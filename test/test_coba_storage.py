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
Tests for ``coba.storage``.
"""

import cStringIO
import os
import shutil
import tempfile
import time

from nose.tools import eq_ as eq, ok_ as ok, raises

from coba import Revision
from coba.crypto import CryptoProvider
from coba.storage import *
from coba.utils import sha1


def _fake_revision(store, path):
    return Revision(store, path, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)


class TestRevisionStore(object):
    """
    Tests for ``coba.storage.Store``.
    """
    def setup(self):
        self.path = tempfile.mkdtemp()
        self.driver = local_storage_driver(self.path)
        self.store = Store(self.driver, 'container', CryptoProvider())

    def teardown(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def test_set_get_append_revisions(self):
        """
        Test setting, getting and appending revisions.
        """
        p = '/foo/bar'
        eq(self.store.get_revisions(p), [])
        rev1 = _fake_revision(self.store, p)
        rev2 = _fake_revision(self.store, p)
        self.store.set_revisions(p, [rev1, rev2])
        revs = self.store.get_revisions(p)
        eq(revs, [rev1, rev2])
        rev3 = self.store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        revs = self.store.get_revisions(p)
        eq(revs, [rev1, rev2, rev3])

    def test_put_get_content(self):
        """
        Test storing and retrieving content.
        """
        content = 'foobar'
        hash = self.store.put_content(cStringIO.StringIO(content))
        eq(hash, sha1(content))
        eq(self.store.get_content(hash).read(), content)

    @raises(KeyError)
    def test_get_content_keyerror(self):
        self.store.get_content('does not exist')

    def test_paths_are_hashed(self):
        """
        Test that paths are hashed.
        """
        p = '/foo/bar'
        rev = self.store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        for root, filenames, dirnames in os.walk(self.path):
            for name in filenames + dirnames:
                n = name.lower()
                ok('foo' not in n)
                ok('bar' not in n)

    @raises(ValueError)
    def test_invalid_store(self):
        """
        Test that an invalid store raises a ``ValueError``.
        """
        self.driver.create_container('invalid')
        Store(self.driver, 'invalid', None)

