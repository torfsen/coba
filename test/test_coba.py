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
        self.storage_dir = os.path.join(self.temp_dir, 'storage')
        self.coba = None

    def teardown(self):
        if self.coba:
            self.coba.stop(block=5)
        shutil.rmtree(self.temp_dir)

    def watch(self, *args, **kwargs):
        idle_wait_time = kwargs.pop('idle_wait_time', 0)
        dirs = [os.path.join(self.temp_dir, d) for d in args]
        for d in dirs:
            self.mkdir(d)
        driver = local_storage_driver(self.storage_dir)
        self.coba = Coba(driver, watched_dirs=dirs,
                         idle_wait_time=idle_wait_time,
                         pid_dir=self.temp_dir)
        self.coba.start(block=5)

    def mkdir(self, path):
        try:
            os.makedirs(os.path.join(self.temp_dir, path))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    def write(self, path, content=''):
        path = os.path.join(self.temp_dir, path)
        self.mkdir(os.path.dirname(path))
        with codecs.open(path, 'w', encoding='utf8') as f:
            f.write(content)
        return _hash(content)

    def file(self, path):
        return self.coba.file(os.path.join(self.temp_dir, path))

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

    def test_file_modification(self):
        self.write('foo/bar', 'bazinga')
        self.watch('foo')
        hash = self.write('foo/bar', 'new')
        self.wait()
        f = self.file('foo/bar')
        revs = f.get_revisions()
        eq(len(revs), 1)
        eq(revs[0].hashsum, hash)

