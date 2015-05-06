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
Tests for ``coba`` which require root privileges.

The tests in this module require root privileges to change the owner of
files (``chown``). This is necessary to check that Coba's owner tracking
correct works as expected.

The tests also require Coba-specific users and user groups which can be
created and removed using the ``create_test_users.sh`` and
``remove_test_users.sh`` scripts, respectively.

If the tests are executed without the necessary privileges or if the
test users and groups are not available then the tests are automatically
skipped.
"""

import errno
import os

from nose.tools import eq_ as eq, ok_ as ok
from nose.plugins.skip import SkipTest

from .test_coba import BaseTest, user_a, user_b, group_a, group_b
from .test_watchdog import (RecordingEventHandler, temp_dir, create_file,
                            watched_dir)
from watchdog.events import FileModifiedEvent

class TestCobaSudo(BaseTest):
    """
    Tests for ``coba.Coba`` which require root privileges.
    """
    def test_owner_change(self):
        """
        Backup due to change of owner.
        """
        self.write('foo/bar', 'bazinga')
        self.chown('foo/bar', user_a, group_a)
        self.watch('foo')
        self.chown('foo/bar', user_b, -1)
        self.wait()
        revs = self.revs('foo/bar')
        eq(len(revs), 1)
        eq(revs[0].owner_id, user_b)
        eq(revs[0].owner_name, 'coba_test_b')
        eq(revs[0].group_id, group_a)
        eq(revs[0].group_name, 'coba_test_a')

    def test_group_change(self):
        """
        Back up due to change of group.
        """
        self.write('foo/bar', 'bazinga')
        self.chown('foo/bar', user_a, group_a)
        self.watch('foo')
        self.chown('foo/bar', -1, group_b)
        self.wait()
        revs = self.revs('foo/bar')
        eq(len(revs), 1)
        eq(revs[0].owner_id, user_a)
        eq(revs[0].owner_name, 'coba_test_a')
        eq(revs[0].group_id, group_b)
        eq(revs[0].group_name, 'coba_test_b')

    def test_restore_file_other_owner(self):
        """
        Restore a file to a different owner.
        """
        self.check_restore(old_owner=user_a, new_owner=user_b)

    def test_restore_file_other_group(self):
        """
        Restore a file to a different group.
        """
        self.check_restore(old_group=group_a, new_group=group_b)

    def test_restore_file_no_owner(self):
        """
        Restore a file without restoring its owner.
        """
        self.check_restore(old_owner=user_a, new_owner=user_b,
                           old_group=group_a, new_group=group_b,
                           owner=False)

    def test_restore_file_no_group(self):
        """
        Restore a file without restoring its group.
        """
        self.check_restore(old_group=group_a, new_group=group_b,
                           old_owner=user_a, new_owner=user_b,
                           group=False)


#
# Watchdog tests that check if owner changes create the necessary events.
#

def test_that_owner_change_creates_modification_events():
    if not user_a:
        raise SkipTest()
    handler = RecordingEventHandler()
    try:
        with temp_dir() as base_dir:
            foo_path = os.path.join(base_dir, 'foo')
            create_file(foo_path)
            os.chown(foo_path, user_a, -1)
            with watched_dir(base_dir, handler):
                os.chown(foo_path, user_b, -1)
    except OSError as e:
        if e.errno == errno.EPERM:
            raise SkipTest()
        raise

    foo_modified = False
    for event in handler.events:
        if isinstance(event, FileModifiedEvent):
            if event.src_path == foo_path:
                foo_modified = True
    ok(foo_modified, 'No modification event for owner change')


def test_that_group_change_creates_modification_events():
    if not group_a:
        raise SkipTest()
    handler = RecordingEventHandler()
    try:
        with temp_dir() as base_dir:
            foo_path = os.path.join(base_dir, 'foo')
            create_file(foo_path)
            os.chown(foo_path, -1, group_a)
            with watched_dir(base_dir, handler):
                os.chown(foo_path, -1, group_b)
    except OSError as e:
        if e.errno == errno.EPERM:
            raise SkipTest()
        raise

    foo_modified = False
    for event in handler.events:
        if isinstance(event, FileModifiedEvent):
            if event.src_path == foo_path:
                foo_modified = True
    ok(foo_modified, 'No modification event for group change')

