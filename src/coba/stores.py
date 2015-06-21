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
Data stores based on LibCloud_ storage.

.. _LibCloud: https://libcloud.apache.org
"""

import json
import gzip
import hashlib
import tempfile

import libcloud.storage.types
import libcloud.storage.drivers.local

from . import Revision
from .utils import binary_file_iterator, make_dirs, normalize_path, to_json


__all__ = [
    'local_storage_driver',
    'RevisionStore',
]


def _get_container(driver, name):
    """
    Get a container, create it if necessary.
    """
    try:
        return driver.get_container(name)
    except libcloud.storage.types.ContainerDoesNotExistError:
        return driver.create_container(name)


def _download_to_temp_file(container, objname):
    """
    Download LibCloud object into temporary file.

    Returns an open file object.
    """
    obj = container.get_object(objname)
    temp_file = tempfile.TemporaryFile()
    for block in obj.as_stream():
        temp_file.write(block)
    temp_file.seek(0)
    return temp_file


def _upload_from_file(container, objname, f):
    """
    Upload file content to a LibCloud object.
    """
    iterator = binary_file_iterator(f)
    container.upload_object_via_stream(iterator, objname)


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


def _hash_and_compress(f, block_size=2**20):
    """
    Hash and compress a file's content.

    The content of the open file-like object ``f`` is read, hashed,
    and compressed in a temporary file. The uncompressed content's hash
    and the open temporary file are returned. Note that the temporary
    file is automatically deleted once its handle is closed.
    """
    hasher = hashlib.sha1()
    temp_file = tempfile.TemporaryFile()
    with gzip.GzipFile(filename='', fileobj=temp_file, mode='wb') as gzip_file:
        while True:
            block = f.read(block_size)
            if not block:
                break
            hasher.update(block)
            gzip_file.write(block)
    temp_file.seek(0)
    return hasher.hexdigest(), temp_file


class _AutoCloseGzipFile(gzip.GzipFile):
    """
    Like ``gzip.GzipFile``, but automatically closes the underlying file.
    """
    def close(self):
        fileobj = self.fileobj
        super(_AutoCloseGzipFile, self).close()
        if fileobj:
            fileobj.close()


class RevisionStore(object):
    """
    Store for revision content and meta-data.
    """
    META_PREFIX = 'meta'
    BLOB_PREFIX = 'blobs'

    def __init__(self, driver, container_name):
        self._container = _get_container(driver, container_name)

    def _path2key(self, path):
        """
        Create meta-data key from file path.
        """
        path = str(normalize_path(path))
        assert path.startswith('/')
        return self.META_PREFIX + path

    def _hash2key(self, hash):
        """
        Create blob key from content hash.
        """
        return self.BLOB_PREFIX + '/' + hash

    def get_revisions(self, path):
        """
        Returns a path's revisions.
        """
        key = self._path2key(path)
        try:
            data = json.loads(self._get_string(key))
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
        self._put_string(key, to_json(data))

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
        hash, compressed_file = _hash_and_compress(f)
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
            temp_file = _download_to_temp_file(self._container, key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError(hash)
        return _AutoCloseGzipFile(filename='', fileobj=temp_file, mode='rb')

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

