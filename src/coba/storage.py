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
import io
import json
import os
import tempfile
import zlib

import libcloud.storage.types
import libcloud.storage.drivers.local

from . import Revision
from .crypto import is_encrypted
from .utils import (binary_file_iterator, make_dirs, normalize_path, sha1,
                    to_json)
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


def _hash_and_compress_file(f, hasher=None, block_size=2**20):
    """
    Hash and compress a file's content.

    The content of the open file-like object ``f`` is read, hashed,
    and compressed in a temporary file. The uncompressed content's hash
    and the open temporary file are returned. Note that the temporary
    file is automatically deleted once its handle is closed.

    ``hasher`` is a hasher from :py:mod:`hashlib` (default:
    :py:class:`hashlib.sha1`).
    """
    hasher = hasher or hashlib.sha1()
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


class _HashingFile(object):
    """
    File-wrapper that hashes content while reading.

    Wrap around an open file-like object, read data via the wrapper and
    use :py:meth:`_HashingFile.hexdigest` to get a hex digest of the hash
    of the data read so far.
    """
    def __init__(self, f, hasher=None):
        """
        Constructor.

        ``f`` is an open file-like object and ``hasher`` is a hasher from
        :py:mod:`hashlib` (default: :py:class:`hashlib.sha1`).
        """
        self._file = f
        self._hasher = hasher or hashlib.sha1()

    def hexdigest(self):
        """
        Hex digest of the hash of the data read so far.
        """
        return self._hasher.hexdigest()

    def read(self, *args, **kwargs):
        data = self._file.read(*args, **kwargs)
        self._hasher.update(data)
        return data


def _decompress_file(input_file, block_size=2**20):
    """
    Decompress file to temporary file.

    ``input_file`` is an open file-like object containing
    zlib-compressed data. The data is decompressed and stored in a
    temporary file, a handle to that file is returned. The temporary
    file is automatically deleted once that handle is closed.
    """
    temp_file = tempfile.TemporaryFile()
    decompressor = zlib.decompressobj()
    while True:
        data = input_file.read(block_size)
        if not data:
            break
        temp_file.write(decompressor.decompress(data))
    temp_file.write(decompressor.flush())
    temp_file.seek(0)
    return temp_file


def _download_to_temp_file(container, objname):
    """
    Download LibCloud object into temporary file.

    Returns an open file object with its file pointer at the beginning
    of the file. The temporary file is deleted automatically once the
    file object is closed.
    """
    obj = container.get_object(objname)
    temp_file = tempfile.TemporaryFile()
    for block in obj.as_stream():
        temp_file.write(block)
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


def _make_salt(n=64):
    """
    Create a cryptographically secure salt string.

    Returns a Unicode string containing ``n`` secure random bytes
    encoded as a hex string.
    """
    return binascii.hexlify(os.urandom(n)).decode('ascii')


class Store(object):
    """
    Store for revision content and meta-data.
    """
    _FORMAT_VERSION = 1             # Store layout format version
    _SETTINGS_PREFIX  = 'settings'  # Directory prefix for settings
    _META_PREFIX = 'meta'           # Directory prefix for meta-data
    _BLOB_PREFIX = 'blobs'          # Directory prefix for content blobs
    _SALT_PREFIX = 'salts'          # Directory prefix for filename salts
    _HASH_ALGO = 'sha1'             # Hash algorithm
    _HASH_ROUNDS = 100000           # Number of rounds for salted hashes
    _SALT_LENGTH = 16               # Length of salts in bytes

    _HASH_CLASS = getattr(hashlib, _HASH_ALGO)

    def __init__(self, driver, container_name, crypto_provider):
        """
        Constructor.

        ``driver`` is a :py:class:`libcloud.storage.base.StorageDriver`
        instance and ``container_name`` is the name of the container to
        use for the store. If the container exists the store contained
        in it will be loaded (if the container doesn't contain a valid
        store then a :py:class:`ValueError` is thrown). If the
        container does not exist then it is created and a new store is
        initialized in it.

        ``crypto_provider`` is a :py:class:`coba.crypto.CryptoProvider`
        instance. If it has a recipient set then all revision and file
        data uploaded to the store is encrypted using the recipient's
        public key.
        """
        try:
            self._load_store(driver, container_name)
        except libcloud.storage.types.ContainerDoesNotExistError:
            self._create_store(driver, container_name)
        except KeyError:
            raise ValueError(('The container "%s" exists but is not a valid ' +
                             'Coba store.') % container_name)
        self.crypto_provider = crypto_provider

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
        self._format_version = self._set_setting(
            'format_version', self._FORMAT_VERSION)

    def _load_store(self, driver, container_name):
        """
        Load existing store in a LibCloud container.
        """
        self._container = driver.get_container(container_name)
        self._format_version = self._get_setting('format_version')
        if self._format_version > self._FORMAT_VERSION:
            raise ValueError(('Store uses the storage format version %d ' +
                             'which is from a newer version of Coba and ' +
                             'not supported in this version.') %
                             self._format_version)

    def _get_path_salt(self, path):
        path = str(normalize_path(path))
        hash = sha1(path)
        key = '%s/%s/%s' % (self._SALT_PREFIX, hash[:2], hash[2:4])
        try:
            salts = json.loads(self._get_data(key))
        except KeyError:
            salts = {}
        try:
            return salts[path]
        except KeyError:
            salts[path] = salt = _make_salt(self._SALT_LENGTH)
            self._put_data(key, to_json(salts))
            return salt

    def _hash_path(self, path):
        path = str(normalize_path(path))
        salt = self._get_path_salt(path)
        return self._salted_hash(path, salt)

    def _salted_hash(self, s, salt):
        """
        Hash a string using a cryptographically secure hash function.

        Returns a Unicode string with the hash encoded as a hex string.
        """
        h = pbkdf2_hmac(self._HASH_ALGO, s, salt, self._HASH_ROUNDS)
        return binascii.hexlify(h).decode('ascii')

    def _path2key(self, path):
        """
        Create meta-data key from file path.
        """
        hash = self._hash_path(path)
        return '%s/%s/%s/%s' % (self._META_PREFIX, hash[:2], hash[2:4],
                                hash[4:])

    def _hash2key(self, hash):
        """
        Create blob key from content hash.
        """
        return '%s/%s/%s/%s' % (self._BLOB_PREFIX, hash[:2], hash[2:4],
                                hash[4:])

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
        self._put_raw_data(self._setting2key(name), to_json(value))
        return value

    def _get_setting(self, name):
        """
        Get a setting from the store.

        Raises a :py:class:`KeyError` if the setting does not exist.
        """
        try:
            return json.loads(self._get_raw_data(self._setting2key(name)))
        except KeyError:
            raise KeyError(name)

    def get_revisions(self, path):
        """
        Returns a path's revisions.
        """
        key = self._path2key(path)
        try:
            data = json.loads(self._get_data(key))
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
        self._put_data(key, to_json(data))

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

        If :py:attr:`Store.crypto_provider` has a recipient set then
        the file content is encrypted using the recipient's public key.
        """
        if self.crypto_provider.recipient:
            hash, source_file = self._hash_and_encrypt_file(f)
        else:
            hash, source_file = _hash_and_compress_file(f, self._HASH_CLASS())
        key = self._hash2key(hash)
        _upload_from_file(self._container, key, source_file)
        return hash

    def _hash_and_encrypt_file(self, f):
        """
        Hash file content and encrypt it.

        The content of the open file-like object ``f`` is hashed and
        encrypted. The return value is a pair of the hash and a file
        handle to a temporary file containing the encrypted data. The
        temporary file is automatically deleted once the file handle is
        closed.
        """
        hashing_file = _HashingFile(f, self._HASH_CLASS())
        temp_file = tempfile.TemporaryFile()
        self.crypto_provider.encrypt(hashing_file, temp_file)
        temp_file.seek(0)
        return hashing_file.hexdigest(), temp_file

    def _decrypt_file(self, f):
        """
        Decrypt file content.

        The content of the open file-like object ``f`` is decrypted. The
        return value is a file handle to a temporary file containing the
        decrypted data. The temporary file is automatically deleted once
        that file handle is closed.
        """
        temp_file = tempfile.TemporaryFile()
        self.crypto_provider.decrypt(f, temp_file)
        temp_file.seek(0)
        return temp_file

    def _encrypt_string(self, s):
        """
        Encrypt a string.
        """
        output = io.BytesIO()
        self.crypto_provider.encrypt(io.BytesIO(s), output)
        return output.getvalue()

    def _decrypt_string(self, s):
        """
        Decrypt a string.
        """
        output = io.BytesIO()
        self.crypto_provider.decrypt(io.BytesIO(s), output)
        return output.getvalue()

    def get_content(self, hash):
        """
        Retrieve content.

        Returns the uncompressed and decrypted content stored at the
        given hash in the form of an open file handle to a temporary
        file. The temporary file is automatically deleted when the file
        handle is closed.

        If no content for the given hash can be found a ``KeyError`` is
        raised.
        """
        key = self._hash2key(hash)
        try:
            temp_file = _download_to_temp_file(self._container, key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError(hash)
        try:
            if is_encrypted(temp_file):
                return self._decrypt_file(temp_file)
            else:
                return _decompress_file(temp_file)
        finally:
            temp_file.close()

    def _put_raw_data(self, key, value):
        """
        Put a raw data into the store.
        """
        self._container.upload_object_via_stream(value, key)

    def _get_raw_data(self, key):
        """
        Get a raw data from the store.
        """
        try:
            obj = self._container.get_object(key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError(key)
        return b''.join(obj.as_stream())

    def _get_data(self, key):
        """
        Get data from the store and decompress/decrypt it.
        """
        data = self._get_raw_data(key)
        if is_encrypted(data):
            return self._decrypt_string(data)
        else:
            return _decompress_string(data)

    def _put_data(self, key, value):
        """
        Compress/encrypt data and store it.
        """
        if self.crypto_provider.recipient:
            value = self._encrypt_string(value)
        else:
            value = _compress_string(value)
        self._put_raw_data(key, value)


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

