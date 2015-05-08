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
import grp
import hashlib
import os
import os.path
import pwd
import shutil
import stat
import tempfile
import time

from nose.tools import (eq_ as eq, ok_ as ok, assert_almost_equal,
                        assert_not_almost_equal)
from nose.plugins.skip import SkipTest

from coba import Coba
from coba.config import Configuration


# Look up Coba test users and groups. See the scripts ``create_test_users.sh``
# and ``remove_test_users.sh``.
try:
    user_a = pwd.getpwnam('coba_test_a').pw_uid
    user_b = pwd.getpwnam('coba_test_b').pw_uid
    group_a = grp.getgrnam('coba_test_a').gr_gid
    group_b = grp.getgrnam('coba_test_b').gr_gid
except KeyError:
    user_a = user_b = group_a = group_b = None


def _hash(value):
    hasher = hashlib.sha256()
    hasher.update(value)
    return hasher.hexdigest()


class BaseTest(object):
    """
    Base class for testing ``coba.Coba``.
    """
    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.coba = None

    def teardown(self):
        if self.coba:
            self.coba.stop(block=5)
        for root, filenames, dirnames in os.walk(self.temp_dir):
            for filename in filenames:
                fullname = os.path.join(root, filename)
                os.chmod(fullname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
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

    def set_mtime(self, path, mtime):
        os.utime(self.path(path), (mtime, mtime))

    def get_mtime(self, path):
        return os.path.getmtime(self.path(path))

    def get_mode(self, path):
        return stat.S_IMODE(os.stat(self.path(path)).st_mode)

    def set_mode(self, path, mode):
        os.chmod(self.path(path), mode)

    def file(self, path):
        return self.coba.file(self.path(path))

    def revs(self, path):
        return self.coba.file(self.path(path)).get_revisions()

    def backup(self, path):
        return self.file(path).backup()

    def wait(self, seconds=2):
        time.sleep(seconds)

    def chown(self, path, uid, gid):
        if user_a is None:
            # Coba test users are not available
            raise SkipTest
        try:
            os.chown(self.path(path), uid, gid)
        except OSError as e:
            if e.errno == errno.EPERM:
                raise SkipTest
            raise

    def get_group(self, path):
        return os.stat(self.path(path)).st_gid

    def get_user(self, path):
        return os.stat(self.path(path)).st_uid

    def check_restore(self, target=None, compare_path=None, content=True,
                      mtime=True, mode=True, user=True, group=True,
                      old_user=None, new_user=None, exp_user=None,
                      old_group=None, new_group=None, exp_group=None,
                      rev_attrs=None):
        """
        A general helper for testing the restoration of files.
        """
        rev_attrs = rev_attrs or {}
        f = 'foo/bar'
        if not compare_path:
            compare_path = target or f
        if target:
            target = self.path(target)
        self.watch()
        old_content = 'bazinga'
        self.write(f, old_content)
        old_mode = stat.S_IRUSR | stat.S_IWUSR
        self.set_mode(f, old_mode)
        old_mtime = self.get_mtime(f)
        if old_group:
            self.chown(f, -1, old_group)
        else:
            old_group = self.get_group(f)
        if old_user:
            self.chown(f, old_user, -1)
        else:
            old_user = self.get_user(f)
        self.backup(f)
        new_mode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP
        self.set_mode(f, new_mode)
        new_content = 'foobarius'
        self.write(f, new_content)
        new_mtime = self.get_mtime(f)
        if new_group:
            self.chown(f, -1, new_group)
        else:
            new_group = old_group
        if new_user:
            self.chown(f, new_user, -1)
        else:
            new_user = old_user
        revs = self.revs(f)
        eq(len(revs), 1)
        rev = revs[0]
        for attr, value in rev_attrs.iteritems():
            setattr(rev, attr, value)
        rev.restore(target=target, content=content, mtime=mtime, mode=mode,
                    user=user, group=group)
        eq(self.read(compare_path), old_content if content else new_content)
        assert_almost_equal(self.get_mtime(compare_path), old_mtime if mtime
                            else new_mtime, delta=0.1)
        eq(self.get_mode(compare_path), old_mode if mode else new_mode)
        exp_group = exp_group or (old_group if group else new_group)
        eq(self.get_group(compare_path), exp_group)
        exp_user = exp_user or (old_user if user else new_user)
        eq(self.get_user(compare_path), exp_user)
        if compare_path != f:
            eq(self.read(f), new_content)
            assert_almost_equal(self.get_mtime(f), new_mtime)
            eq(self.get_mode(f), new_mode)
            eq(self.get_group(f), new_group)
            eq(self.get_user(f), new_user)


class TestCoba(BaseTest):
    """
    Tests for ``coba.Coba``.
    """

    def test_file_creation(self):
        """
        Backup due to creation of a file.
        """
        self.watch('foo')
        hash = self.write('foo/bar', 'bazinga')
        self.wait()
        revs = self.revs('foo/bar')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_empty_file_creation(self):
        """
        Backup due to creation of an empty file.
        """
        self.watch('foo')
        hash = self.write('foo/bar')
        self.wait()
        revs = self.revs('foo/bar')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_file_modification(self):
        """
        Backup due to content modification.
        """
        self.write('foo/bar', 'bazinga')
        self.watch('foo')
        hash = self.write('foo/bar', 'new')
        self.wait()
        revs = self.revs('foo/bar')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_mtime_modification(self):
        """
        Backup due to mtime modification.
        """
        hash = self.write('foo/bar', 'bazinga')
        self.watch('foo')
        self.set_mtime('foo/bar', 10)
        self.wait()
        revs = self.revs('foo/bar')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)
        eq(revs[0].mtime, 10)

    def test_mode_modification(self):
        """
        Backup due to mode modification.
        """
        hash = self.write('foo/bar', 'bazinga')
        self.set_mode('foo/bar', stat.S_IRUSR)
        self.watch('foo')
        mode = stat.S_IRUSR | stat.S_IWUSR
        self.set_mode('foo/bar', mode)
        self.wait()
        revs = self.revs('foo/bar')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)
        eq(revs[0].mode, mode)

    def test_file_move_within_watch(self):
        """
        Backup due to file being moved within a watch.
        """
        hash = self.write('foo/bar', 'bazinga')
        self.watch('foo')
        self.move('foo/bar', 'foo/baz')
        self.wait()
        revs = self.revs('foo/baz')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_file_move_between_watches(self):
        """
        Backup due to file being moved between watches.
        """
        hash = self.write('foo/bar', 'bazinga')
        self.watch('foo', 'foz')
        self.move('foo/bar', 'foz/bar')
        self.wait()
        revs = self.revs('foz/bar')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_file_move_into_watch(self):
        """
        Backup due to file being moved into a watch.
        """
        hash = self.write('foo/bar', 'bazinga')
        self.watch('foz')
        self.move('foo/bar', 'foz/bar')
        self.wait()
        revs = self.revs('foz/bar')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_directory_move_within_watch(self):
        """
        Backup due to directory being moved within a watch.
        """
        hash = self.write('foo/bar/qux', 'bazinga')
        self.watch('foo')
        self.move('foo/bar', 'foo/baz')
        self.wait()
        revs = self.revs('foo/baz/qux')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_directory_move_between_watches(self):
        """
        Backup due to directory being moved between watches.
        """
        hash = self.write('foo/bar/qux', 'bazinga')
        self.watch('foo', 'foz')
        self.move('foo/bar', 'foz/bar')
        self.wait()
        revs = self.revs('foz/bar/qux')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_directory_move_into_watch(self):
        """
        Backup due to directory being moved into a watch.
        """
        hash = self.write('foo/bar/qux', 'bazinga')
        self.watch('foz')
        self.move('foo/bar', 'foz/bar')
        self.wait()
        revs = self.revs('foz/bar/qux')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_restore_file_no_content(self):
        """
        Restore a file without restoring its content.
        """
        self.check_restore(content=False)

    def test_restore_file_no_mtime(self):
        """
        Restore a file without restoring its mtime.
        """
        self.check_restore(mtime=False)

    def test_restore_file_no_mode(self):
        """
        Restore a file without restoring its permissions.
        """
        self.check_restore(mode=False)

    def test_restore_file_in_place(self):
        """
        Restore a file in-place.
        """
        self.check_restore()

    def test_restore_file_other_file(self):
        """
        Restore a file to a different file.
        """
        self.check_restore(target='foo/baz')

    def test_restore_file_other_dir(self):
        """
        Restore a file to a different directory.
        """
        path = self.mkdir('foz')
        self.check_restore(target=path, compare_path=os.path.join(path, 'bar'))

    def test_restore_file_no_content_not_existing(self):
        """
        Restore a non-existing file without restoring its content.
        """
        self.watch()
        hash = self.write('foo/bar', 'bazinga')
        self.backup('foo/bar')
        revs = self.revs('foo/bar')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)
        target = revs[0].restore(target=self.path('foo/baz'), content=False)
        ok(not target.exists())

    def test_ignore_file(self):
        """
        Ignore files.
        """
        self.watch('foo', ignored=['**/*.bar'])
        self.write('foo/bar.bar', 'bazinga')
        hash = self.write('foo/bar.baz', 'bazinga')
        self.wait()
        eq(len(self.revs('foo/bar.bar')), 0)
        revs = self.revs('foo/bar.baz')
        eq(len(revs), 1)
        eq(revs[0].content_hash, hash)

    def test_backup_file_size(self):
        """
        Backups store file size.
        """
        self.watch()
        f = 'foo/bar'
        self.write(f, '1')
        self.backup(f)
        self.write(f, '12')
        self.backup(f)
        self.write(f, '123')
        self.backup(f)
        revs = self.revs(f)
        eq(len(revs), 3)
        eq(revs[0].size, 1)
        eq(revs[1].size, 2)
        eq(revs[2].size, 3)

