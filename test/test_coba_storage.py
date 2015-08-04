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

from test_coba_crypto import GPG_KEY_DIR, needs_gpgme


def _fake_revision(store, path):
    return Revision(store, path, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)


class TestRevisionStore(object):
    """
    Tests for ``coba.storage.Store``.
    """
    def setup(self):
        self.path = tempfile.mkdtemp()
        self.driver = local_storage_driver(self.path)

    def make_store(self, recipient=None):
        crypto_provider = CryptoProvider(recipient, GPG_KEY_DIR)
        return Store(self.driver, 'container', crypto_provider)

    def teardown(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def test_set_get_append_revisions(self):
        """
        Test setting, getting and appending revisions.
        """
        store = self.make_store()
        p = '/foo/bar'
        eq(store.get_revisions(p), [])
        rev1 = _fake_revision(store, p)
        rev2 = _fake_revision(store, p)
        store.set_revisions(p, [rev1, rev2])
        revs = store.get_revisions(p)
        eq(revs, [rev1, rev2])
        rev3 = store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        revs = store.get_revisions(p)
        eq(revs, [rev1, rev2, rev3])

    def test_put_get_content(self):
        """
        Test storing and retrieving content.
        """
        store = self.make_store()
        content = 'foobar'
        hash = store.put_content(cStringIO.StringIO(content))
        eq(hash, sha1(content))
        eq(store.get_content(hash).read(), content)

    @raises(KeyError)
    def test_get_content_keyerror(self):
        """
        Test that getting non-existing content raises ``KeyError``.
        """
        self.make_store().get_content('does not exist')

    def test_paths_are_hashed(self):
        """
        Test that paths are hashed.
        """
        store = self.make_store()
        p = '/foo/bar'
        rev = store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        for root, filenames, dirnames in os.walk(self.path):
            for name in filenames + dirnames:
                n = name.lower()
                ok('foo' not in n)
                ok('bar' not in n)

    @raises(ValueError)
    def test_invalid_store(self):
        """
        Test that an invalid store raises ``ValueError``.
        """
        self.driver.create_container('invalid')
        Store(self.driver, 'invalid', None)

    @needs_gpgme
    def test_mixing_encrypted_and_non_encrypted_content(self):
        """
        Test mixing encrypted and non-encrypted content.
        """
        p = '/foo/bar'
        store = self.make_store()
        rev1 = store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        store = self.make_store('test@coba')
        eq(store.get_revisions(p), [rev1])
        rev2 = store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        store = self.make_store()
        eq(store.get_revisions(p), [rev1, rev2])
        rev3 = store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        store = self.make_store('test@coba')
        eq(store.get_revisions(p), [rev1, rev2, rev3])

