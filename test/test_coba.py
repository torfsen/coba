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
Tests for ``coba``.
"""

import codecs
import errno
import hashlib
import os
import os.path
import shutil
import tempfile
import time

from nose.tools import eq_ as eq, ok_ as ok

from coba import Coba
from coba.config import Configuration
from coba.stores import local_storage_driver


def _hash(value):
    hasher = hashlib.sha256()
    hasher.update(value)
    return hasher.hexdigest()


class Test_Coba(object):
    """
    Tests for ``coba.Coba``.
    """

    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.coba = None

    def teardown(self):
        if self.coba:
            self.coba.stop(block=5)
        shutil.rmtree(self.temp_dir)

    def path(self, p):
        return os.path.join(self.temp_dir, p)

    def watch(self, *args, **kwargs):
        config_args = {
            'storage_dir': self.path('storage'),
            'idle_wait_time': 0,
            'pid_dir': self.temp_dir,
            'watched_dirs': [self.path(d) for d in args],
        }
        config_args.update(kwargs)
        config = Configuration(**config_args)
        for d in config.watched_dirs:
            self.mkdir(d)
        self.coba = Coba(config)
        self.coba.start(block=5)

    def mkdir(self, path):
        path = self.path(path)
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        return path

    def write(self, path, content=''):
        path = self.path(path)
        self.mkdir(os.path.dirname(path))
        with codecs.open(path, 'w', encoding='utf8') as f:
            f.write(content)
        return _hash(content)

    def read(self, path):
        path = self.path(path)
        with codecs.open(path, 'r', encoding='utf8') as f:
            return f.read()

    def move(self, src, target):
        src = self.path(src)
        target = self.path(target)
        os.rename(src, target)

    def file(self, path):
        return self.coba.file(self.path(path))

    def wait(self, seconds=2):
        time.sleep(seconds)

    def test_file_creation(self):
        self.watch('foo')
        hash = self.write('foo/bar', 'bazinga')
        self.wait()
        f = self.file('foo/bar')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_empty_file_creation(self):
        self.watch('foo')
        hash = self.write('foo/bar')
        self.wait()
        f = self.file('foo/bar')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_file_modification(self):
        self.write('foo/bar', 'bazinga')
        self.watch('foo')
        hash = self.write('foo/bar', 'new')
        self.wait()
        f = self.file('foo/bar')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_file_move_within_watch(self):
        hash = self.write('foo/bar', 'bazinga')
        self.watch('foo')
        self.move('foo/bar', 'foo/baz')
        self.wait()
        f = self.file('foo/baz')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_file_move_between_watches(self):
        hash = self.write('foo/bar', 'bazinga')
        self.watch('foo', 'foz')
        self.move('foo/bar', 'foz/bar')
        self.wait()
        f = self.file('foz/bar')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_file_move_into_watch(self):
        hash = self.write('foo/bar', 'bazinga')
        self.watch('foz')
        self.move('foo/bar', 'foz/bar')
        self.wait()
        f = self.file('foz/bar')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_directory_move_within_watch(self):
        hash = self.write('foo/bar/qux', 'bazinga')
        self.watch('foo')
        self.move('foo/bar', 'foo/baz')
        self.wait()
        f = self.file('foo/baz/qux')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_directory_move_between_watches(self):
        hash = self.write('foo/bar/qux', 'bazinga')
        self.watch('foo', 'foz')
        self.move('foo/bar', 'foz/bar')
        self.wait()
        f = self.file('foz/bar/qux')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_directory_move_into_watch(self):
        hash = self.write('foo/bar/qux', 'bazinga')
        self.watch('foz')
        self.move('foo/bar', 'foz/bar')
        self.wait()
        f = self.file('foz/bar/qux')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

    def test_restore_file_in_place(self):
        self.watch('foo')
        hash = self.write('foo/bar', 'bazinga')
        self.wait()
        self.write('foo/bar', 'buz')
        self.wait()
        f = self.file('foo/bar')
        revs = f.get_revisions()
        eq(len(revs), 2)
        eq(revs[0].hashsum, hash)
        revs[0].restore()
        eq(self.read('foo/bar'), 'bazinga')

    def test_restore_file_other_file(self):
        self.watch('foo')
        hash = self.write('foo/bar', 'bazinga')
        self.wait()
        self.write('foo/bar', 'buz')
        self.wait()
        f = self.file('foo/bar')
        revs = f.get_revisions()
        eq(len(revs), 2)
        eq(revs[0].hashsum, hash)
        revs[0].restore(target=self.path('foo/baz'))
        eq(self.read('foo/baz'), 'bazinga')
        eq(self.read('foo/bar'), 'buz')

    def test_restore_file_other_dir(self):
        self.watch('foo')
        hash = self.write('foo/bar', 'bazinga')
        self.wait()
        self.write('foo/bar', 'buz')
        self.wait()
        f = self.file('foo/bar')
        revs = f.get_revisions()
        eq(len(revs), 2)
        eq(revs[0].hashsum, hash)
        path = self.mkdir('foz')
        revs[0].restore(target=path)
        eq(self.read('foz/bar'), 'bazinga')
        eq(self.read('foo/bar'), 'buz')

    def test_ignore_file(self):
        self.watch('foo', ignored=['**/*.bar'])
        self.write('foo/bar.bar', 'bazinga')
        hash = self.write('foo/bar.baz', 'bazinga')
        self.wait()
        f = self.file('foo/bar.bar')
        eq(len(f.get_revisions()), 0)
        f = self.file('foo/bar.baz')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

