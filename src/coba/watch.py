#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

# Copyright (c) 2015 Florian Brucker (mail@florianbrucker.de).
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
File-system watching.
"""

import functools
import logging
import os.path
import sys
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
    events (from :py:class:`EventHandler`) and the storage of the
    corresponding file modifications (by :py:class:`StorageThread`).

    Iteration over an instance yields active files in the order of their
    unprocessed modifications in an infinite loop (when there are no
    active files the iterator blocks). Use the :py:meth:`join` method to
    automatically exit the loop once all files have been processed.
    """

    def __init__(self, logger, idle_wait_time=5):
        """
        Constructor.

        ``logger`` is an instance of :py:class:`logging.Logger` and
        ``idle_wait_time`` is the time (in seconds) to wait after
        receiving a file modification event before dispatching the file
        for backup.
        """
        self._logger = logger
        self.idle_wait_time = idle_wait_time
        self._queue = pqdict.PQDict()
        self._stop = False
        self.lock = threading.RLock()
        self.is_not_empty = threading.Condition(self.lock)

    def register_file_modification(self, path):
        """
        Register a file's modification.

        This schedules the file for backup.
        """
        path = str(normalize_path(path))
        with self.is_not_empty:
            self._queue[path] = time.time() + self.idle_wait_time
            self._logger.info('File "%s" was modified.' % path)
            self.is_not_empty.notify_all()

    def register_file_deletion(self, path):
        """
        Register a file's deletion.

        If the file was previously scheduled for backup but not backed
        up, yet, then it is unscheduled.
        """
        path = str(normalize_path(path))
        with self.is_not_empty:
            try:
                del self._queue[path]
                self._logger.info(('Previously modified file "%s" was ' +
                                  'removed before backup.') % path)
                self.is_not_empty.notify_all()
            except KeyError:
                pass

    def register_directory_deletion(self, path):
        """
        Register a directory's deletion.

        Any scheduled but so far unprocessed files within the directory
        are unscheduled.
        """
        path = str(normalize_path(path))
        with self.is_not_empty:
            for key in self._queue.keys():
                if is_in_dir(key, path):
                    del self._queue[key]
                    self._logger.info(('Previously modified file "%s" was ' +
                                      'removed before backup.') % key)
            self.is_not_empty.notify_all()

    def next(self):
        """
        Get next file to be processed.

        This method returns the file with the oldest unprocessed
        modification. If there are no active files then the call blocks
        until the next call to :py:meth:`register_event` is made. See
        :py:meth:`join` for breaking the block.
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
                    self._logger.debug('Dispatching "%s" for processing.' %
                                       path)
                    return path
            self._queue[path] = target_time  # Reschedule
            self._logger.debug(('Waiting for %f seconds before processing ' +
                               '"%s".') % (pause, path))
            time.sleep(pause)

    def __iter__(self):
        return self

    def join(self):
        """
        Block until queue is empty.

        This method blocks until the list of active files is empty.
        Once this is the case, calling :py:meth:`next` raises
        :py:class:`StopIteration` instead of blocking. Blocking calls to
        :py:meth:`next` that were made before the call to
        :py:meth:`join` are terminated in the same way.

        New events are still accepted while the active files are being
        processed. Make sure to first stop the event provider before
        calling :py:meth:`join`, otherwise the event provider might keep
        :py:meth:`join` from exiting by always adding new events.
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
    def __init__(self, queue, is_ignored, logger):
        """
        Constructor.

        ``queue`` is an instance of :py:class:`FileQueue`.

        ``is_ignored`` is a function that, given a file path, returns
        ``True`` if the file is to be ignored and ``False`` otherwise.

        ``logger`` is a :py:class:`logging.Logger` instance.
        """
        super(EventHandler, self).__init__()
        self._queue = queue
        self._is_ignored = is_ignored
        self._logger = logger

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
            return  # Don't dispatch
        super(EventHandler, self).dispatch(event)

    def on_created(self, event):
        self._register_file_modification(event.src_path)

    on_modified = on_created

    def on_deleted(self, event):
        self._queue.register_file_deletion(event.src_path)

    def _register_file_modification(self, path):
        if not self._is_ignored(path):
            self._queue.register_file_modification(path)

    def on_moved(self, event):
        self._queue.register_file_deletion(event.src_path)
        # Watchdog only generates move events for moves within the same
        # watch. In that case, it generates no separate creation or
        # modification events for the destinations.
        self._register_file_modification(event.dest_path)


class StorageThread(threading.Thread):
    """
    Thread for storing file modifications.

    File modifications are taken from the file queue and stored.
    """
    def __init__(self, queue, backup, logger, *args, **kwargs):
        """
        Constructor.

        ``queue`` is an instance of :py:class:`FileQueue`.

        ``backup`` is a callable that takes a file path and backs up
        the file.

        ``logger`` is a :py:class:`logging.Logger` instance.
        """
        super(StorageThread, self).__init__(*args, **kwargs)
        self._queue = queue
        self._backup = backup
        self._logger = logger

    def run(self):
        for path in self._queue:
            try:
                self._logger.debug('Backing up "%s".' % path)
                self._backup(path)
                self._logger.info('Backed up "%s".' % path)
            except Exception:
                self._logger.exception('Error while backing up "%s".' % path)


def _fix_threading_exception_bug():
    """
    Fixes the exception handling of :py:class:`threading.Thread`.

    Any uncaught exception should cause :py:func:`sys.excepthook` to be
    called. However, this does not work for exceptions thrown in threads
    created via :py:class:`threading.Thread`, see
    https://bugs.python.org/issue1230540.

    This method fixes that problem using the workaround given in the
    bugreport above: It monkey-patches
    :py:meth:`threading.Thread.__init__`` to dynamically replace a
    thread's :py:meth:`threading.Thread.run` method with an
    error-handling wrapper. The wrapper takes care of calling
    :py:func:`sys.excepthook` for uncaught exceptions. Monkey-patching
    ``__init__`` instead of ``run`` is necessary to make the fix work
    for subclasses of ``Thread``.

    Thread instances created before this method is called are not
    covered by the fix.
    """
    old_init = threading.Thread.__init__

    @functools.wraps(old_init)
    def new_init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        old_run = self.run

        @functools.wraps(old_run)
        def run(*args, **kwargs):
            try:
                old_run(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                sys.excepthook(*sys.exc_info())

        self.run = run

    threading.Thread.__init__ = new_init


class Service(service.Service):
    """
    The Coba backup daemon.
    """
    def __init__(self, backup, config):
        """
        Constructor.

        ``backup`` is a function that takes a filename and backs up
        that file.

        ``config`` is an instance of
        :py:class:`coba.config.Configuration`.
        """
        super(Service, self).__init__('coba', pid_dir=config.pid_dir)
        self._backup = backup
        self._config = config
        self._observers = []
        self._init_logging()

    def _init_logging(self):
        handler = logging.FileHandler(self._config.log_file, encoding='utf8')
        format = '%(asctime)s <%(levelname)s> %(message)s'
        handler.setFormatter(logging.Formatter(format, '%Y-%m-%d %H:%M:%S'))
        self.logger.addHandler(handler)
        self.logger.setLevel(self._config.log_level)

    def _install_exception_hook(self):
        def hook(type, value, traceback):
            self.logger.error(str(value), exc_info=(type, value, traceback))
        sys.excepthook = hook
        _fix_threading_exception_bug()

    def _start(self):
        self.logger.info('Starting backup daemon...')
        self._queue = FileQueue(self.logger, self._config.idle_wait_time)
        self.logger.debug('Starting observers...')
        self._event_handler = EventHandler(
            self._queue, self._config.is_ignored, self.logger)
        for dir in self._config.watched_dirs:
            observer = watchdog.observers.Observer()
            dir = os.path.abspath(str(dir))
            self.logger.info('Watching "%s".' % dir)
            observer.schedule(self._event_handler, dir, recursive=True)
            self._observers.append(observer)
        for observer in self._observers:
            observer.start()
        self.logger.debug('Starting storage thread...')
        self._storage_thread = StorageThread(self._queue, self._backup,
                                             self.logger)
        self._storage_thread.start()
        self.logger.info('Backup daemon is running.')

    def _stop(self):
        self.logger.info('Shutdown of backup daemon initiated...')
        self.logger.debug('Stopping observers...')
        for observer in self._observers:
            observer.stop()
        self.logger.debug('Waiting for observers to finish...')
        for observer in self._observers:
            observer.join()
        self.logger.debug('Waiting for file queue to finish...')
        self._queue.join()
        self.logger.debug('Waiting for storage thread to finish...')
        self._storage_thread.join()
        self.logger.info('Backup daemon has been shutdown.')

    def run(self):
        self._install_exception_hook()
        self._start()
        self.wait_for_sigterm()
        self._stop()

