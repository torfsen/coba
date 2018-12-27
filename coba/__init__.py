#!/usr/bin/env python3

# Copyright (c) 2018 Florian Brucker (mail@florianbrucker.de).
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

import collections
import logging
from pathlib import Path
import threading
import time

import watchdog
import watchdog.events


__version__ = '0.0.1'


log = logging.getLogger(__name__)


# Internally, ``Path`` instances are used for all file and directory paths. Raw
# paths obtained from outside are converted at the point they are obtained at.
# When external functions expect raw paths then ``Path`` instances are converted
# at the last possible moment.


# Seconds to wait for another modification before backing up a file
IDLE_WAIT_SECONDS = 5


class DictQueue:
    '''
    A dict-like queue.
    '''
    def __init__(self):
        self._dict = collections.OrderedDict()

    def __setitem__(self, key, value):
        try:
            self._dict.move_to_end(key)
        except KeyError:
            pass
        self._dict[key] = value

    def __getitem__(self, key):
        return self._dict[key]

    def __len__(self):
        return len(self._dict)

    def __contains__(self, key):
        return key in self._dict

    def pop_oldest_item(self):
        '''
        Remove and return the oldest item.
        '''
        try:
            oldest_key = next(iter(self._dict.keys()))
        except StopIteration:
            raise ValueError('DictQueue is empty')
        return self._dict.popitem(oldest_key)


class FileQueue:
    '''
    Takes file system events and provides files to be backed up.

    Not every file system event results in a backup: for example, if a
    file is quickly modified several times then only the last version of
    the file is backed up.
    '''
    def __init__(self):
        self._queue = DictQueue()
        self._condition = threading.Condition()

    def register_file_modification(self, path):
        '''
        Register a file modification event.
        '''
        with self._condition:
            self._queue[path] = time.time()
            self._condition.notify()
            log.debug('{} has been modified'.format(path))

    def __next__(self):
        '''
        Return the next file to be backed up.
        '''
        while True:
            with self._condition:
                while not self._queue:
                    self._condition.wait()
                path, modification_time = self._queue.pop_oldest_item()
            backup_time = modification_time + IDLE_WAIT_SECONDS
            time.sleep(max(0, backup_time - time.time()))
            with self._condition:
                if path in self._queue:
                    # The file has been modified while we were waiting
                    log.debug('{} is still being modified'.format(path))
                    continue
                return path

    def __iter__(self):
        return self


class EventHandler(watchdog.events.FileSystemEventHandler):
    '''
    Event handler for file system events.
    '''
    # We do not care about deletion events, since we do not store deletions. If
    # a file is removed between being scheduled for backup and the backup
    # itself then this is handled in the backup code.

    def __init__(self, queue):
        '''
        Constructor.

        ``queue`` is an instance of ``FileQueue``.
        '''
        super().__init__()
        self._queue = queue

    def dispatch(self, event):
        if event.is_directory:
            # TODO: Think about directory renames/moves: The "deletion" part
            #       is of no interest to us, but we need to handle the creation
            #       of the target files -- do we get separate creation events
            #       for these?
            return  # Ignore directory events
        super().dispatch(event)

    def on_created(self, event):
        self._register(Path(event.src_path))

    def on_modified(self, event):
        self._register(Path(event.src_path))

    def _register(self, path):
        self._queue.register_file_modification(path)

    def on_moved(self, event):
        # Watchdog only generates move events for moves within the same
        # watch. In that case, it generates no separate creation or
        # modification events for the destinations.
        self._register(Path(event.dest_path))

