#!/usr/bin/env python

"""
File-system watching.
"""

import threading
import time

import pqdict
import service
import watchdog.observers
import watchdog.events

from .utils import normalize_path


class Event(object):
    """
    A timed file modification event.
    """
    def __init__(self, path, t=None):
        self.path = normalize_path(path)
        self.time = t or time.time()

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self.__dict__ != other.__dict__


class FileQueue(object):
    """
    Queue for active files.

    This class provides the communication between incoming file system
    events (from ``EventHandler``) and the storage of the corresponding
    file modifications (by ``StorageDaemon``).

    Iteration over an instance yields active files in the order of their
    unprocessed modifications in an infinite loop (when there are no
    active files the iterator blocks). Use the ``join`` method to
    automatically exit the loop once all files have been processed.
    """
    def __init__(self, idle_wait_time=5):
        self.idle_wait_time = idle_wait_time
        self._queue = pqdict.PQDict()
        self._stop = False
        self.lock = threading.RLock()
        self.is_not_empty = threading.Condition(self.lock)

    def register_event(self, event):
        """
        Add a file modification event to the queue.
        """
        with self.is_not_empty:
            self._queue[str(event.path)] = event.time + self.idle_wait_time
            print 'Registered event for "%s".' % event.path
            self.is_not_empty.notify_all()

    def next(self):
        """
        Get next file to be processed.

        This method returns the file with the oldest unprocessed
        modification. If there are no active files then the call blocks
        until the next call to ``register_event`` is made. See ``join``
        for breaking the block.
        """
        while True:
            with self.is_not_empty:
                while not self._queue:
                    if self._stop:
                        self._stop = False  # Allow restart
                        raise StopIteration
                    self.is_not_empty.wait(1)
                path, target_time = self._queue.popitem()
                pause = target_time - time.time()
                if pause <= 0:
                    self.is_not_empty.notify_all()
                    print 'Dispatching "%s" for processing.' % path
                    return path
            self._queue[path] = target_time  # Reschedule
            print 'Waiting for %f seconds before processing "%s".' % (
                  pause, path)
            time.sleep(pause)

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
            while self._queue:
                self.is_not_empty.wait()


class EventHandler(watchdog.events.FileSystemEventHandler):
    """
    Event handler for file system events.
    """
    # Deletion events are ignored because we only store file content,
    # not directory content. Creation events are ignored because they
    # are followed by modification events. Directory events are ignored
    # because we only track files.

    def __init__(self, queue):
        super(EventHandler, self).__init__()
        self._queue = queue

    def dispatch(self, event):
        if event.is_directory:
            return
        super(EventHandler, self).dispatch(event)

    def on_modified(self, event):
        self._queue.register_event(Event(event.src_path))

    def on_moved(self, event):
        # For moves we don't care about the source file, because from
        # the source file's point of view being moved is equivalent to
        # being deleted (and we don't care about deletions).
        self._queue.register_event(Event(event.dest_path))


class StorageThread(threading.Thread):
    """
    Daemon for storing file modifications.

    File modifications are taken from the file queue and stored.
    """
    def __init__(self, queue, backup, *args, **kwargs):
        """
        Constructor.

        ``queue`` is a queue of active files (see ``FileQueue``).

        ``backup`` is a callable that takes a file path and backs up
        the file.
        """
        super(StorageThread, self).__init__(*args, **kwargs)
        self._queue = queue
        self._backup = backup

    def run(self):
        for path in self._queue:
            try:
                self._backup(path)
                print 'Backed up "%s".' % path
            except Exception as e:
                print 'Error while backing up "%s": %s' % (path, e)


class Watcher(object):
    """
    File system watcher.

    File system events are observed and backups are made of modified
    files. Both of these processes run in separate threads.
    """

    def __init__(self, coba):
        self._queue = FileQueue(coba.idle_wait_time)
        self._event_handler = EventHandler(self._queue)
        self._observers = []
        for dir in coba.watched_dirs:
            observer = watchdog.observers.Observer()
            observer.schedule(self._event_handler, str(dir), recursive=True)
            self._observers.append(observer)

        def backup(path):
            coba.file(path).backup()

        self._storage_thread = StorageThread(self._queue, backup)

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
        self._queue.join()
        print "Waiting for storage thread to finish."
        self._storage_thread.join()
        print "Watcher is stopped."

