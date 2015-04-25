#!/usr/bin/env python

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
        self.storage_dir = self.path('storage')
        self.coba = None

    def teardown(self):
        if self.coba:
            self.coba.stop(block=5)
        shutil.rmtree(self.temp_dir)

    def path(self, p):
        return os.path.join(self.temp_dir, p)

    def watch(self, *args, **kwargs):
        idle_wait_time = kwargs.pop('idle_wait_time', 0)
        dirs = [self.path(d) for d in args]
        for d in dirs:
            self.mkdir(d)
        driver = local_storage_driver(self.storage_dir)
        self.coba = Coba(driver, watched_dirs=dirs,
                         idle_wait_time=idle_wait_time,
                         pid_dir=self.temp_dir)
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

    def wait(self, seconds=1):
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

    def test_file_move_between_watchs(self):
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

