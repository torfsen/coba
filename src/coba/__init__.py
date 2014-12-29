#!/usr/bin/env python

"""
Continuous backups.
"""

import threading
import time

import pqdict
import watchdog.observers
import watchdog.events


# Seconds to wait before storing a modified file.
WAIT = 5


class _EVENT_TYPES(object):
    """
    Event types from the ``watchdog`` module.
    """
    CREATED = 'created'
    DELETED = 'deleted'
    MODIFIED = 'modified'
    MOVED = 'moved'


class ActiveFile(object):
    """
    A file that has been modified and which is being processed.
    """

    def __init__(self, path, event, t=None):
        self.lock = threading.Lock()
        self.path = path
        self.t0 = t or time.time()
        self.t1 = None
        self.event = event

    def _touch(self, event, t=None):
        with self.lock:
            self.t1 = t or time.time()
            self.event = event

    def _reset(self):
        with self.lock:
            self.t0 = self.t1
            self.t1 = None


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

    def __init__(self):
        self._files = {}
        self._queue = pqdict.PQDict()
        self._stop = False
        self.lock = threading.RLock()
        self.is_not_empty = threading.Condition(self.lock)
        self.is_stopping = threading.Condition(self.lock)

    def touch(self, event, t=None):
        """
        Mark a file as modified.
        """
        with self.is_not_empty:
            try:
                self._files[event.src_path]._touch(event, t)
            except KeyError:
                f = ActiveFile(event.src_path, event, t)
                self._files[event.src_path] = f
                self._queue[event.src_path] = f.t0
                self.is_not_empty.notify_all()

    def processed(self, path):
        """
        Mark a file as processed.
        """
        with self.lock:
            f = self._files.pop(path)
            if f.t1:
                # File has been touched since processing started, reschedule
                print '"%s" has been modified while being processed, rescheduling.' % path
                self.touch(f.event, f.t1)
            else:
                print '"%s" has been processed.' % path

    def next(self):
        """
        Get next file to be processed.

        This method returns the file with the oldest unprocessed
        modification. If there are no active files then the call blocks
        until the next call to ``touch`` is made. See ``join`` for
        breaking the block.
        """
        with self.is_not_empty:
            while not self._queue:
                if self._stop:
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

    def __init__(self, files):
        super(EventHandler, self).__init__()
        self._files = files

    def on_any_event(self, event):
        if event.is_directory or event.event_type == _EVENT_TYPES.CREATED:
            # Dictionary events are ignored because we only track
            # files. Creation events are ignored because they are
            # automatically followed by a corresponding modification
            # event.
            return
        self._files.touch(event)
        print 'Registered modification of "%s" (%s).' % (event.src_path,
                                                         event.event_type)


class Storage(object):
    """
    Storage system for recording file modifications.
    """

    def store_modification(self, path, t=None):
        t = t or time.time()
        print 'Storing modification of "%s".' % path
        time.sleep(5)

    def store_deletion(self, path, t=None):
        # From the ``watchdog`` docs:
        #
        #     Since the Windows API does not provide information about
        #     whether an object is a file or a directory, delete events
        #     for directories may be reported as a file deleted event.
        t = t or time.time()
        print 'Storing deletion of "%s".' % path
        time.sleep(5)

    def store_move(self, src_path, dest_path, t=None):
        t = t or time.time()
        print 'Storing move of "%s" to "%s".' % (src_path, dest_path)
        time.sleep(5)


class StorageDaemon(threading.Thread):
    """
    Daemon for storing file modifications.

    File modifications are taken from the event list (see
    ``ActiveFiles``) and stored (see ``Storage``). To avoid storing
    frequently changing files too often there is a minimum pause
    between storage operations for the same file (see ``WAIT``).
    """

    def __init__(self, storage, files, *args, **kwargs):
        super(StorageDaemon, self).__init__(*args, **kwargs)
        self._storage = storage
        self._files = files

    def run(self):
        for f in self._files:
            pause = f.t0 + WAIT - time.time()
            if pause > 0:
                time.sleep(pause)
            f._reset()
            # FIXME: We need to compare the event type after the pause
            # with the one from before the pause. If they differ we need
            # to make sure that they are "compatible": MODIFIED -> MODIFIED is
            # OK, but MODIFIED -> DELETED and similar stuff needs special
            # attention. It is probably OK to simply use the latest event type
            # but that should be double-checked.
            if f.event.event_type == _EVENT_TYPES.MODIFIED:
                self._storage.store_modification(f.path)
            elif f.event.event_type == _EVENT_TYPES.DELETED:
                self._storage.store_deletion(f.path)
            elif f.event.event_type == _EVENT_TYPES.MOVED:
                self._storage.store_move(f.path, f.event.dest_path)
            else:
                raise ValueError('Unknown event type %r.' % f.event.event_type)
            self._files.processed(f.path)


def main(path='.'):
    files = ActiveFiles()
    storage = Storage()

    event_handler = EventHandler(files)
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    storage_daemon = StorageDaemon(storage, files)
    storage_daemon.start()

    print "Waiting for events."
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print "Received CTRL+C, stopping observer."
        observer.stop()
    print "Waiting for observer to process remaining events."
    observer.join()
    print "Waiting for storage handler to process remaining files."
    files.join()
    storage_daemon.join()
    print "Done."
