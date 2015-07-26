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
Data storage based on LibCloud_.

.. _LibCloud: https://libcloud.apache.org
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from future.builtins import *
from future.builtins.disabled import *

import binascii
import io
import json
import hashlib
import os
import tempfile
import zlib

import libcloud.storage.types
import libcloud.storage.drivers.local

from . import Revision
from .utils import binary_file_iterator, make_dirs, normalize_path, to_json
from .compat import pbkdf2_hmac


__all__ = [
    'local_storage_driver',
    'Store',
]



def _upload_from_file(container, objname, f):
    """
    Upload file content to a LibCloud object.
    """
    iterator = binary_file_iterator(f)
    container.upload_object_via_stream(iterator, objname)


def _hash_and_compress_file(f, block_size=2**20):
    """
    Hash and compress a file's content.

    The content of the open file-like object ``f`` is read, hashed,
    and compressed in a temporary file. The uncompressed content's hash
    and the open temporary file are returned. Note that the temporary
    file is automatically deleted once its handle is closed.
    """
    hasher = hashlib.sha1()
    temp_file = tempfile.TemporaryFile()
    compressor = zlib.compressobj(9)
    while True:
        block = f.read(block_size)
        if not block:
            break
        hasher.update(block)
        temp_file.write(compressor.compress(block))
    temp_file.write(compressor.flush())
    temp_file.seek(0)
    return hasher.hexdigest(), temp_file


def _download_to_temp_file_and_decompress(container, objname):
    """
    Download LibCloud object into temporary file.

    Returns an open file object.
    """
    obj = container.get_object(objname)
    temp_file = tempfile.TemporaryFile()
    decompressor = zlib.decompressobj()
    for block in obj.as_stream():
        temp_file.write(decompressor.decompress(block))
    temp_file.write(decompressor.flush())
    temp_file.seek(0)
    return temp_file


def _compress_string(s):
    """
    Compress a string using zlib.
    """
    return zlib.compress(s)


def _decompress_string(s):
    """
    Decompress a string using zlib.
    """
    return zlib.decompress(s)


def _make_salt():
    """
    Create a cryptographically secure salt string.

    Returns a Unicode string containing 64 secure random bytes encoded
    as a hex string.
    """
    return unicode(binascii.hexlify(os.urandom(64)))


class Store(object):
    """
    Store for revision content and meta-data.
    """
    _FORMAT_VERSION = 1
    _SETTINGS_PREFIX  = 'settings'
    _META_PREFIX = 'meta'
    _BLOB_PREFIX = 'blobs'
    _HASH_ALGO = 'sha256'
    _HASH_ROUNDS = 100000

    def __init__(self, driver, container_name):
        """
        Constructor.

        ``driver`` is a :py:class:`libcloud.storage.base.StorageDriver`
        instance and ``container_name`` is the name of the container to
        use for the store. If the container exists the store contained
        in it will be loaded (if the container doesn't contain a valid
        store then a :py:class:`ValueError` is thrown). If the
        container does not exist then it is created and a new store is
        initialized in it.
        """
        try:
            self._load_store(driver, container_name)
        except libcloud.storage.types.ContainerDoesNotExistError:
            self._create_store(driver, container_name)
        except KeyError:
            raise ValueError(('The container "%s" exists but is not a valid ' +
                             'Coba store.') % container_name)

    @property
    def salt(self):
        """
        The salt used for hashing paths.
        """
        return self._salt

    @property
    def format_version(self):
        """
        The storage format version used by the store.
        """
        return self._format_version

    def _create_store(self, driver, container_name):
        """
        Create and initialize store in a LibCloud container.
        """
        self._container = driver.create_container(container_name)
        self._salt = self._set_setting('salt', _make_salt())
        self._format_version = self._set_setting(
            'format_version', self._FORMAT_VERSION)

    def _load_store(self, driver, container_name):
        """
        Load existing store in a LibCloud container.
        """
        self._container = driver.get_container(container_name)
        self._format_version = self._get_setting('format_version')
        if self._format_version > self._FORMAT_VERSION:
            raise ValueError('Store uses the storage format version %d ' +
                             'which is from a newer version of Coba and ' +
                             'not supported in this version.' %
                             self._format_version)
        self._salt = self._get_setting('salt')

    def _hash(self, s):
        """
        Hash a string using a cryptographically secure hash function.

        Returns a Unicode string with the hash encoded as a hex string.
        """
        h = pbkdf2_hmac(self._HASH_ALGO, s, self._salt, self._HASH_ROUNDS)
        return unicode(binascii.hexlify(h))

    def _path2key(self, path):
        """
        Create meta-data key from file path.
        """
        path = str(normalize_path(path))
        return self._META_PREFIX + '/' + self._hash(path)

    def _hash2key(self, hash):
        """
        Create blob key from content hash.
        """
        return self._BLOB_PREFIX + '/' + hash

    def _setting2key(self, setting):
        """
        Create settings key from settings name.
        """
        return self._SETTINGS_PREFIX + '/' + setting

    def _set_setting(self, name, value):
        """
        Store a setting in the store.

        Returns the setting's value.
        """
        self._put_json(self._setting2key(name), value)
        return value

    def _get_setting(self, name):
        """
        Get a setting from the store.

        Raises a :py:class:`KeyError` if the setting does not exist.
        """
        try:
            return self._get_json(self._setting2key(name))
        except KeyError:
            raise KeyError(name)

    def get_revisions(self, path):
        """
        Returns a path's revisions.
        """
        key = self._path2key(path)
        try:
            data = self._get_compressed_json(key)
        except KeyError:
            return []
        path = data['path']
        return [Revision(self, path=path, **d) for d in data['revisions']]

    def set_revisions(self, path, revisions):
        """
        Set a path's revisions.

        ``revisions`` is a list of :py:class:`Revision` instances for
        the given path.
        """
        path = str(normalize_path(path))
        key = self._path2key(path)
        data = {
            'path': path,
            'revisions': revisions,
        }
        self._put_compressed_json(key, data)

    def append_revision(self, path, *args, **kwargs):
        """
        Create a new revision for a path.

        Creates a new instance of :py:class:`Revision` for the given
        path. All arguments are passed on to the :py:class:`Revision`
        constructor. The revision is stored and returned.

        The revision's content blob must be stored separately using
        :py:meth:`put_content`.
        """
        revision = Revision(self, path, *args, **kwargs)
        revisions = self.get_revisions(path)
        revisions.append(revision)
        self.set_revisions(path, revisions)
        return revision

    def put_content(self, f):
        """
        Store content from a file.

        ``f`` is an open file-like object. Its content is read, hashed,
        compressed, and stored. The return value is the hash which can
        then be used to retrieve the data again using
        :py:meth:`get_content`.
        """
        hash, compressed_file = _hash_and_compress_file(f)
        key = self._hash2key(hash)
        _upload_from_file(self._container, key, compressed_file)
        return hash

    def get_content(self, hash):
        """
        Retrieve content.

        Returns the uncompressed content stored at the given hash in
        the form of an open file handle to a temporary file. The
        temporary file is automatically deleted when the file handle
        is closed.

        If no content for the given hash can be found a ``KeyError`` is
        raised.
        """
        key = self._hash2key(hash)
        try:
            return _download_to_temp_file_and_decompress(self._container, key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError(hash)

    def _get_string(self, key):
        """
        Get a raw string from the store.
        """
        try:
            obj = self._container.get_object(key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError(key)
        return ''.join(obj.as_stream())

    def _put_string(self, key, value):
        """
        Put a raw string into the store.
        """
        self._container.upload_object_via_stream(value, key)

    def _put_compressed_json(self, key, value):
        """
        Encode data to JSON, compress and store it.
        """
        self._put_string(key, _compress_string(to_json(value)))

    def _get_compressed_json(self, key):
        """
        Get compressed JSON data, decompress and decode it.
        """
        return json.loads(_decompress_string(self._get_string(key)))

    def _put_json(self, key, value):
        """
        Encode data to JSON and store it.
        """
        self._put_string(key, to_json(value))

    def _get_json(self, key):
        """
        Get JSON data and decode it.
        """
        return json.loads(self._get_string(key))


def local_storage_driver(path):
    """
    Create a local LibCloud storage driver.

    ``path`` is the directory in which the data is stored. It is
    automatically created if it does not exist.

    Returns an instance of
    :py:class:`libcloud.storage.drivers.local.LocalStorageDriver`.
    """
    make_dirs(path)
    return libcloud.storage.drivers.local.LocalStorageDriver(path)
