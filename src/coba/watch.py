#!/usr/bin/env python

"""
File-system watching.
"""

import threading
import time

import pqdict
import watchdog.observers
import watchdog.events


class Event(object):
    """
    A timed file modification event.
    """

    def __init__(self, path, t=None):
        self.path = path
        self.time = t or time.time()

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self.__dict__ != other.__dict__


class ActiveFiles(object):
    """
    Manager for active files.

    This class provides the communication between incoming file system
    events (from ``EventHandler``) and the storage of the corresponding
    file modifications (by ``StorageDaemon``).

    Iteration over an instance yields active files in the order of their
    unprocessed modifications in an infinite loop (when there are no
    active files the iterator blocks). Use the ``join`` method to
    automatically exit the loop once all files have been processed.
    """

    def __init__(self, coba):
        self._coba = coba
        self._files = {}
        self._queue = pqdict.PQDict()
        self._stop = False
        self.lock = threading.RLock()
        self.is_not_empty = threading.Condition(self.lock)
        self.is_stopping = threading.Condition(self.lock)

    def register_event(self, event):
        """
        Add a file modification event to the queue.
        """
        with self.is_not_empty:
            try:
                f = self._files[event.path]
            except KeyError:
                f = self._coba.file(event.path)
                self._files[event.path] = f
                self.is_not_empty.notify_all()
            f._register_event(event)
            self._queue[event.path] = event.time
            print 'Registered event for "%s".' % event.path

    def processed(self, path):
        """
        Mark a file as processed.
        """
        with self.lock:
            f = self._files.pop(path)
            if f._force_backup:
                # Backup was forced, reschedule to capture second modification
                print 'Rescheduling "%s" after forced backup.' % f.path
                self.register_event(f._event, f._event.time)
            else:
                print '"%s" has been processed.' % path

    def next(self):
        """
        Get next file to be processed.

        This method returns the file with the oldest unprocessed
        modification. If there are no active files then the call blocks
        until the next call to ``register_event`` is made. See ``join``
        for breaking the block.
        """
        with self.is_not_empty:
            while not self._queue:
                if self._stop:
                    self._stop = False  # Allow restart
                    raise StopIteration
                self.is_not_empty.wait(1)
            return self._files[self._queue.popitem()[0]]

    def __iter__(self):
        return self

    def join(self):
        """
        Block until queue is empty.

        This method blocks until the list of active files is empty.
        Once this is the case, calling ``next`` raises ``StopIteration``
        instead of blocking. Blocking calls to ``next`` that were made
        before the call to ``join`` are terminated in the same way.

        New events are still accepted while the active files are being
        processed. Make sure to first stop the event provider before
        calling ``join``, otherwise the event provider might keep
        ``join`` from exiting by always adding new events.
        """
        with self.is_not_empty:
            self._stop = True
            self.is_stopping.notify_all()
            while self._queue:
                    self.is_not_empty.wait()


class EventHandler(watchdog.events.FileSystemEventHandler):
    """
    Event handler for file system events.
    """

    # Deletion events are ignored because we only store file content,
    # not directory content.
    # Creation events are ignored because they are followed by
    # modification events.

    def __init__(self, files):
        super(EventHandler, self).__init__()
        self._files = files

    def dispatch(self, event):
        if event.is_directory:
            # Dictionary events are ignored because we only track files
            return
        super(EventHandler, self).dispatch(event)

    def on_modified(self, event):
        self._files.register_event(Event(event.src_path))

    def on_moved(self, event):
        # For moves we don't care about the source file, because from
        # the source file's point of view being moved is equivalent to
        # being deleted (and we don't care about deletions).
        self._files.register_event(Event(event.src_path))


class StorageThread(threading.Thread):
    """
    Daemon for storing file modifications.

    File modifications are taken from the event list (see
    ``ActiveFiles``) and stored. To avoid storing a file during an
    ongoing modification there is a mechanism to wait until a file
    is idle.
    """

    def __init__(self, files, idle_wait_time, *args, **kwargs):
        """
        Constructor.

        ``files`` is a queue of active files (see ``ActiveFiles``).

        ``idle_wait_time`` is the time in seconds that a file must be
        unmodified after a previous modification before a backup is
        done. This is to prevent backups during ongoing file
        modifications.
        """
        super(StorageThread, self).__init__(*args, **kwargs)
        self._idle_wait_time = idle_wait_time
        self._files = files

    def _process(self, f):
        """
        Backup a file and mark it as processed.
        """
        f.backup()
        self._files.processed(str(f.path))

    def run(self):
        for f in self._files:
            if f._force_backup:
                self._process(f)
            else:
                event = f._event
                pause = event.time + self._idle_wait_time - time.time()
                print ('Waiting until "%s" is idle (pausing for %f seconds).' %
                       (f.path, max(pause, 0)))
                if pause > 0:
                    time.sleep(pause)
                if f._event == event or f._force_backup:
                    # Either no further modification happened during
                    # the pause or the event belongs to a new
                    # modification.
                    self._process(f)
                else:
                    # File was modified again while waiting for it to
                    # be idle, we reschedule.
                    print ('Rescheduling "%s" due to ongoing modification' %
                          f.path)
                    self._files.register_event(f._event)


class Watcher(object):
    """
    File system watcher.

    File system events are observed and backups are made of modified
    files. Both of these processes run in separate threads.
    """

    def __init__(self, coba):
        self._files = ActiveFiles(coba)
        self._event_handler = EventHandler(self._files)
        self._observers = []
        for dir in coba.watched_dirs:
            observer = watchdog.observers.Observer()
            observer.schedule(self._event_handler, str(dir), recursive=True)
            self._observers.append(observer)
        self._storage_thread = StorageThread(self._files, coba.idle_wait_time)

    def start(self):
        """
        Start the watcher.
        """
        print "Starting observers."
        for observer in self._observers:
            observer.start()
        print "Starting storage thread."
        self._storage_thread.start()

    def stop(self):
        """
        Stop the watcher and block until shutdown is complete.
        """
        print "Stopping observers."
        for observer in self._observers:
            observer.stop()
        print "Waiting for observers to finish."
        for observer in self._observers:
            observer.join()
        print "Waiting for file queue to finish."
        self._files.join()
        print "Waiting for storage thread to finish."
        self._storage_thread.join()
        print "Watcher is stopped."

