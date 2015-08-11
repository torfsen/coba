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

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from future.builtins import *
from future.builtins.disabled import *

import io
import os
import os.path
import shutil
import tempfile
import time

from nose.tools import eq_ as eq, ok_ as ok, raises

from coba import Revision
from coba.crypto import CryptoProvider, is_encrypted
from coba.storage import *
from coba.utils import sha1

from .test_coba_crypto import GOT_GPGME, GPG_KEY_DIR, needs_gpgme
from .utils import parameterized


def _fake_revision(store, path):
    return Revision(store, path, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)


recipients = [(None,)]
if GOT_GPGME:
    recipients.append(('test@coba',))


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

    @parameterized(recipients)
    def test_set_get_append_revisions(self, recipient):
        """
        Setting, getting and appending revisions.
        """
        store = self.make_store(recipient)
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

    @parameterized(recipients)
    def test_put_get_content(self, recipient):
        """
        Storing and retrieving content.
        """
        store = self.make_store(recipient)
        content = 'foobar'
        hash = store.put_content(io.BytesIO(content))
        eq(hash, sha1(content))
        eq(store.get_content(hash).read(), content)

    @parameterized(recipients)
    @raises(KeyError)
    def test_get_content_keyerror(self, recipient):
        """
        Getting non-existing content raises ``KeyError``.
        """
        self.make_store(recipient).get_content('does not exist')

    @parameterized(recipients)
    def test_paths_are_hashed(self, recipient):
        """
        Paths are hashed.
        """
        store = self.make_store(recipient)
        p = '/foo/bar'
        rev = store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        for root, filenames, dirnames in os.walk(self.path):
            for name in filenames + dirnames:
                n = name.lower()
                ok('foo' not in n)
                ok('bar' not in n)

    @needs_gpgme
    def test_files_are_encrypted(self):
        """
        Files in the store are encrypted.
        """
        store = self.make_store('test@coba')
        p = '/foo/bar'
        rev = store.append_revision(p, time.time(), 1, 2, 3, 4, 5, 6, 7, 8)
        content = 'foobar'
        store.put_content(io.BytesIO(content))
        for d in [Store._META_PREFIX, Store._BLOB_PREFIX, Store._SALT_PREFIX]:
            for root, filenames, _ in os.walk(os.path.join(self.path, d)):
                for filename in filenames:
                    with open(os.path.join(root, filename), 'rb') as f:
                        ok(is_encrypted(f))

    @raises(ValueError)
    def test_invalid_store(self):
        """
        An invalid store raises ``ValueError``.
        """
        self.driver.create_container('invalid')
        Store(self.driver, 'invalid', None)

    @needs_gpgme
    def test_mixing_encrypted_and_non_encrypted_content(self):
        """
        Mixing encrypted and non-encrypted content.
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

    @raises(ValueError)
    def test_unsupported_format_version(self):
        """
        Loading a store with an unsupported format version.
        """
        old_format_version = Store._FORMAT_VERSION
        Store._FORMAT_VERSION += 1
        try:
            self.make_store()
        finally:
            Store._FORMAT_VERSION = old_format_version
        self.make_store()

    def test_format_version(self):
        """
        Format version property.
        """
        eq(self.make_store().format_version, 1)

