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

from .utils import is_in_dir, normalize_path


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

    def register_file_modification(self, path):
        """
        Register a file's modification.
        """
        path = str(normalize_path(path))
        with self.is_not_empty:
            self._queue[path] = time.time() + self.idle_wait_time
            print 'File "%s" was modified.' % path
            self.is_not_empty.notify_all()

    def register_file_deletion(self, path):
        """
        Register a file's deletion.
        """
        path = str(normalize_path(path))
        with self.is_not_empty:
            try:
                del self._queue[path]
                print 'Previously modified file "%s" was removed before backup.' % path
                self.is_not_empty.notify_all()
            except KeyError:
                pass

    def register_directory_deletion(self, path):
        """
        Register a directory's deletion.
        """
        path = str(normalize_path(path))
        with self.is_not_empty:
            for key in self._queue.keys():
                if is_in_dir(key, path):
                    del self._queue[key]
                    print 'Previously modified file "%s" was removed before backup.' % key
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
    # Directory events are ignored because we only track files.
    def __init__(self, queue):
        super(EventHandler, self).__init__()
        self._queue = queue

    def dispatch(self, event):
        if event.is_directory:
            # Watchdog's behavior for directory moves depends on whether
            # the destination directory is inside the same watch as the
            # source directory. If that is the case, watchdog generates
            # move events both for the directory and its files. If this
            # is not the case, however, then watchdog only generates a
            # single deletion event for the directory, and no events for
            # its files. In that case we need to manually remove the
            # corresponding items from the queue. Since we cannot check
            # whether a directory deletion event is due to the directory
            # begin deleted (in which case deletion events for its files
            # are being generated by watchdog) or due to the directory
            # being moved to a non-watched directory we do this for any
            # directory deletion event.
            #
            # See https://github.com/gorakhargosh/watchdog/issues/308
            if isinstance(event, watchdog.events.DirDeletedEvent):
                self._queue.register_directory_deletion(event.src_path)
            return
        super(EventHandler, self).dispatch(event)

    def on_created(self, event):
        self._queue.register_file_modification(event.src_path)

    def on_modified(self, event):
        self._queue.register_file_modification(event.src_path)

    def on_deleted(self, event):
        self._queue.register_file_deletion(event.src_path)

    def on_moved(self, event):
        self._queue.register_file_deletion(event.src_path)
        # Watchdog only generates move events for moves within the same
        # watch. In that case, it generates no separate creation or
        # modification events for the destinations.
        self._queue.register_file_modification(event.dest_path)


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

