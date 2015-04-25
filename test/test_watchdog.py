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
Tests for the ``watchdog`` package.

We make some assumptions regarding the generation of file system events
by the ``watchdog`` package. These assumptions are essential to a
correct behavior of Coba, so we explicitly test them here.
"""

import contextlib
import os
import os.path
import shutil
import tempfile
import time

from nose.tools import eq_ as eq, ok_ as ok
from watchdog.observers import Observer
from watchdog.events import (FileSystemEventHandler, FileCreatedEvent,
                             FileDeletedEvent, FileMovedEvent)


class RecordingEventHandler(FileSystemEventHandler):
    """
    Simple file system event handler that records all events.
    """
    def __init__(self):
        super(RecordingEventHandler, self).__init__()
        self.events = []

    def on_any_event(self, event):
        self.events.append(event)


@contextlib.contextmanager
def temp_dir():
    """
    Context manager that creates and removes a temporary directory.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@contextlib.contextmanager
def watched_dir(dir, event_handler):
    """
    Context manager for watching a directory.
    """
    observer = Observer()
    observer.schedule(event_handler, dir, recursive=True)
    observer.start()
    try:
        yield
    finally:
        time.sleep(2)  # Wait until events have been processed
        observer.stop()
        observer.join()


def create_file(path, contents=''):
    """
    Create a file.
    """
    with open(path, 'w') as f:
        f.write(contents)


# We rely on ``watchdog`` to emit file events for the files in a
# directory when the directory is deleted or moved (instead of emitting
# just a single directory event).

def test_that_directory_deletion_creates_file_deletion_events():
    handler = RecordingEventHandler()
    with temp_dir() as d:
        sub_dir = os.path.join(d, 'sub')
        os.mkdir(sub_dir)
        foo_path = os.path.join(sub_dir, 'foo')
        create_file(foo_path)
        bar_path = os.path.join(sub_dir, 'bar')
        create_file(bar_path, 'bar')
        with watched_dir(d, handler):
            shutil.rmtree(sub_dir, ignore_errors=True)

    foo_deleted = False
    bar_deleted = False
    for event in handler.events:
        if isinstance(event, FileDeletedEvent):
            if event.src_path == foo_path:
                foo_deleted = True
            elif event.src_path == bar_path:
                bar_deleted = True
    ok(foo_deleted, 'No file deletion event for empty files')
    ok(bar_deleted, 'No file deletion event for non-empty files')


def test_that_directory_movement_in_same_watch_creates_file_movement_events():
    handler = RecordingEventHandler()
    with temp_dir() as base_dir:
        src_dir = os.path.join(base_dir, 'src')
        os.mkdir(src_dir)
        foo_path = os.path.join(src_dir, 'foo')
        create_file(foo_path)
        bar_path = os.path.join(src_dir, 'bar')
        create_file(bar_path, 'bar')
        with watched_dir(base_dir, handler):
            dest_dir = os.path.join(base_dir, 'dest')
            os.rename(src_dir, dest_dir)

    foo_moved = False
    bar_moved = False
    for event in handler.events:
        if isinstance(event, FileMovedEvent):
            if event.src_path == foo_path:
                foo_moved = True
            elif event.src_path == bar_path:
                bar_moved = True
    ok(foo_moved, 'No file movement event for empty files')
    ok(bar_moved, 'No file movement event for non-empty files')


def test_that_directory_movement_between_watches_creates_creation_events():
    src_handler = RecordingEventHandler()
    dest_handler = RecordingEventHandler()
    with temp_dir() as base_dir:
        src_dir = os.path.join(base_dir, 'src')
        os.mkdir(src_dir)
        sub_dir = os.path.join(src_dir, 'sub')
        os.mkdir(sub_dir)
        foo_src_path = os.path.join(sub_dir, 'foo')
        create_file(foo_src_path)
        bar_src_path = os.path.join(sub_dir, 'bar')
        create_file(bar_src_path, 'bar')
        dest_dir = os.path.join(base_dir, 'dest')
        os.mkdir(dest_dir)
        dest_sub_dir = os.path.join(dest_dir, 'sub')
        with watched_dir(src_dir, src_handler):
            with watched_dir(dest_dir, dest_handler):
                os.rename(sub_dir, dest_sub_dir)
        foo_dest_path = os.path.join(dest_sub_dir, 'foo')
        bar_dest_path = os.path.join(dest_sub_dir, 'bar')

    foo_created = False
    bar_created = False
    for event in dest_handler.events:
        if isinstance(event, FileCreatedEvent):
            if event.src_path == foo_dest_path:
                foo_created = True
            elif event.src_path == bar_dest_path:
                bar_created = True
    ok(foo_created, 'No creation event for empty files')
    ok(bar_created, 'No creation event for non-empty files')
