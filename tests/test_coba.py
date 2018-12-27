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

import logging
from pathlib import Path
import stat
import tempfile
import time
from unittest import mock

import pytest
from sealedmock import seal
from watchdog.events import FileSystemEventHandler
import watchdog.observers

from coba import EventHandler


log = logging.getLogger(__name__)


class Watch(FileSystemEventHandler):
    '''
    Context manager for watching a directory.
    '''
    def __init__(self, path, handler):
        super().__init__()
        self.path = path
        self.handler = handler

    def __enter__(self):
        self._observer = watchdog.observers.Observer()
        self._observer.schedule(self.handler, str(self.path), recursive=True)
        log.debug('Watching {}'.format(self.path))
        self._observer.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        time.sleep(1)
        self._observer.stop()
        try:
            self._observer.join()
        except RuntimeError:
            # Obvserver was never started
            pass


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        yield temp_dir


@pytest.fixture
def queue():
    return mock.Mock()


@pytest.fixture
def watch(temp_dir, queue):
    return Watch(temp_dir, EventHandler(queue))


class TestEventHandler:

    def test_creating_a_file(self, temp_dir, queue, watch):
        with watch:
            file_path = temp_dir / 'test.txt'
            file_path.touch()
        seal(queue)
        queue.register_file_modification.assert_called_once_with(file_path)

    def test_modifying_file_content(self, temp_dir, queue, watch):
        file_path = temp_dir / 'test.txt'
        file_path.touch()
        with watch:
            file_path.write_text('foobar')
        seal(queue)
        queue.register_file_modification.assert_called_once_with(file_path)

    def test_modifying_file_permissions(self, temp_dir, queue, watch):
        file_path = temp_dir / 'test.txt'
        file_path.write_text('foobar')
        with watch:
            file_path.chmod(stat.S_IXUSR)
        seal(queue)
        queue.register_file_modification.assert_called_once_with(file_path)

    def test_moving_a_file_inside_the_watch(self, temp_dir, queue, watch):
        file_path = temp_dir / 'test.txt'
        file_path.write_text('foobar')
        new_path = temp_dir / 'test2.txt'
        with watch:
            file_path.rename(new_path)
        seal(queue)
        queue.register_file_modification.assert_called_once_with(new_path)

    def test_moving_a_file_out_of_the_watch(self, temp_dir, queue, watch):
        file_path = temp_dir / 'test.txt'
        file_path.write_text('foobar')
        with tempfile.TemporaryDirectory() as temp_dir2:
            temp_dir2 = Path(temp_dir2)
            new_path = temp_dir2 / 'test2.txt'
            with watch:
                file_path.rename(new_path)
        seal(queue)
        assert not hasattr(queue, 'register_file_modification')

    def test_moving_a_file_into_the_watch(self, temp_dir, queue, watch):
        with tempfile.TemporaryDirectory() as temp_dir2:
            temp_dir2 = Path(temp_dir2)
            file_path = temp_dir2 / 'test.txt'
            file_path.write_text('foobar')
            new_path = temp_dir / 'test2.txt'
            with watch:
                file_path.rename(new_path)
        seal(queue)
        queue.register_file_modification.assert_called_once_with(new_path)

    def test_deleting_a_file(self, temp_dir, queue, watch):
        file_path = temp_dir / 'test.txt'
        file_path.write_text('foobar')
        with watch:
            file_path.unlink()
        seal(queue)
        assert not hasattr(queue, 'register_file_modification')

    def test_creating_a_directory(self, temp_dir, queue, watch):
        with watch:
            (temp_dir / 'subdir').mkdir()
        seal(queue)
        assert not hasattr(queue, 'register_file_modification')

    def test_modifying_directory_permissions(self, temp_dir, queue, watch):
        dir_path = temp_dir / 'subdir'
        dir_path.mkdir()
        (dir_path / 'test.txt').write_text('foobar')
        with watch:
            dir_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        seal(queue)
        assert not hasattr(queue, 'register_file_modification')

    def test_moving_a_directory_inside_the_watch(self, temp_dir, queue, watch):
        sub_dir = temp_dir / 'subdir'
        sub_dir.mkdir()
        file_path = sub_dir / 'test.txt'
        file_path.write_text('foobar')
        with watch:
            new_dir = temp_dir / 'newdir'
            sub_dir.rename(new_dir)
        seal(queue)
        queue.register_file_modification.assert_called_once_with(
            new_dir / 'test.txt')

    def test_moving_a_directory_out_of_the_watch(self, temp_dir, queue, watch):
        sub_dir = temp_dir / 'subdir'
        sub_dir.mkdir()
        file_path = sub_dir / 'test.txt'
        file_path.write_text('foobar')
        with tempfile.TemporaryDirectory() as temp_dir2:
            temp_dir2 = Path(temp_dir2)
            new_dir = temp_dir2 / 'subdir2'
            with watch:
                sub_dir.rename(new_dir)
        seal(queue)
        assert not hasattr(queue, 'register_file_modification')

    def test_moving_a_directory_into_the_watch(self, temp_dir, queue, watch):
        with tempfile.TemporaryDirectory() as temp_dir2:
            temp_dir2 = Path(temp_dir2)
            sub_dir = temp_dir2 / 'subdir'
            sub_dir.mkdir()
            file_path = sub_dir / 'test.txt'
            file_path.write_text('foobar')
            new_dir = temp_dir / 'subdir2'
            with watch:
                sub_dir.rename(new_dir)
        seal(queue)
        queue.register_file_modification.assert_called_once_with(
            new_dir / 'test.txt')

    def test_deleting_a_directory(self, temp_dir, queue, watch):
        sub_dir = temp_dir / 'subdir'
        sub_dir.mkdir()
        with watch:
            sub_dir.rmdir()
        seal(queue)
        assert not hasattr(queue, 'register_file_modification')

    # TODO: Changing a file/directory's owner

