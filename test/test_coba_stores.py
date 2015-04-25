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
Tests for ``coba.stores``.
"""

import cStringIO
import hashlib
import shutil
import tempfile

from nose.tools import eq_ as eq, ok_ as ok

from coba.stores import *

_unique = object()

_TEXT = "FOO BAR" * 100
_DATA = {'foo':1, 'bar':'boom', 'bazinga':[1, 2, 3]}

def test_CompressTransformer():
    t = CompressTransformer()
    data = cStringIO.StringIO(_TEXT)
    new_key, compressed_file = t.transform(_unique, data)
    compressed_data = compressed_file.read()
    compressed_file.seek(0)
    ok(len(_TEXT) > len(compressed_data))
    eq(new_key, _unique)
    uncompressed_file = t.invert(compressed_file)
    eq(_TEXT, uncompressed_file.read())


def test_CompressAndHashTransformer():
    t = CompressAndHashTransformer()
    hashsum = hashlib.sha256(_TEXT).hexdigest()
    data = cStringIO.StringIO(_TEXT)
    key, compressed_file = t.transform(None, data)
    compressed_data = compressed_file.read()
    compressed_file.seek(0)
    ok(len(_TEXT) > len(compressed_data))
    eq(key, hashsum)
    uncompressed_file = t.invert(compressed_file)
    eq(_TEXT, uncompressed_file.read())


def test_JSONTransformer():
    t = JSONTransformer()
    new_key, new_data = t.transform(_unique, _DATA)
    eq(new_key, _unique)
    ok(hasattr(new_data, 'read'), 'Output is not a file.')
    inverted = t.invert(new_data)
    eq(inverted, _DATA)


def test_ChainedTransformer():
    t1 = JSONTransformer()
    t2 = CompressAndHashTransformer()
    t = ChainedTransformer([t1, t2])
    _, json_file = t1.transform(None, _DATA)
    hashsum = hashlib.sha256(json_file.read()).hexdigest()
    json_file.seek(0)
    _, compressed_file = t2.transform(None, json_file)
    chained_key, chained_data = t.transform(_unique, _DATA)
    eq(chained_key, hashsum)
    eq(chained_data.read(), compressed_file.read())
    chained_data.seek(0)
    inverted = t.invert(chained_data)
    eq(_DATA, inverted)


class StoreTestCase(object):
    """
    Test case which provides a store based on a local temporary
    LibCloud storage driver.
    """

    _STORE_CLASS = None

    def setup(self):
        self.path = tempfile.mkdtemp()
        self.driver = local_storage_driver(self.path)
        self.store = self._STORE_CLASS(self.driver, 'container')

    def teardown(self):
        shutil.rmtree(self.path, ignore_errors=True)


class test_JSONStore(StoreTestCase):

    _STORE_CLASS = JSONStore

    def test(self):
        self.store['foobar'] = _DATA
        eq(self.store['foobar'], _DATA)


class test_BlobStore(StoreTestCase):

    _STORE_CLASS = BlobStore

    def test_put(self):
        hashsum = hashlib.sha256(_TEXT).hexdigest()
        data = cStringIO.StringIO(_TEXT)
        key = self.store.put(data)
        eq(key, hashsum)

    def test_get(self):
        data = cStringIO.StringIO(_TEXT)
        key = self.store.put(data)
        eq(self.store.get(key), _TEXT)

    def test_get_file(self):
        data = cStringIO.StringIO(_TEXT)
        key = self.store.put(data)
        eq(self.store.get_file(key).read(), _TEXT)

