#!/usr/bin/env python

"""
A blob store based on LibCloud storage.
"""

import collections
import cStringIO
import errno
import json
import gzip
import hashlib
import os
import tempfile

import libcloud.storage.drivers.local
import libcloud.storage.types


__all__ = ['BlobStore', 'JSONStore', 'local_storage_driver']


def _get_container(driver, name):
    """
    Get a container, create it if necessary.
    """
    try:
        return driver.get_container(name)
    except libcloud.storage.types.ContainerDoesNotExistError:
        return driver.create_container(name)


def _binary_file_iterator(f, block_size=2**20):
    """
    Generator for iterating over binary files in blocks.

    ``f`` is a file opened in binary mode. The generator reads blocks
    from the file, where ``block_size`` is the maximum block size.
    """
    while True:
        block = f.read(block_size)
        if not block:
            return
        yield block


def _compress_and_upload(container, data, block_size=2**20):
    """
    Compress data, upload it and return hash.

    ``data`` is either a string or an open file-like object. Its
    content is read and compressed to a local temporary file. During
    the compression, the data's hash is computed on the fly.

    Once the data is compressed and the hash is known the compressed
    data is streamed to the given container. The hash is used as the
    object name.
    """
    if not hasattr(data, 'read'):
        # Not a file, assume string
        data = cStringIO.StringIO(data)
    hasher = hashlib.sha1()
    # We need to compress the data to a local file first in order to
    # obtain the data's hash.
    with tempfile.TemporaryFile() as temp_file:
        with gzip.GzipFile(filename='', fileobj=temp_file) as gzip_file:
            while True:
                block = data.read(block_size)
                if not block:
                    break
                hasher.update(block)
                gzip_file.write(block)
        hashsum = hasher.hexdigest()
        temp_file.seek(0)
        iterator = _binary_file_iterator(temp_file)
        container.upload_object_via_stream(iterator, hashsum)
    return hashsum


def _download_and_decompress(container, hashsum):
    """
    Download data and decompress it.

    The data of the object identified by the given hashsum is
    downloaded to a local temporary file and decompressed.

    The return value is an instance of ``gzip.GzipFile`` which
    provides the decompression. The temporary file is deleted
    automatically when the Gzip wrapper file is closed.
    """
    obj = container.get_object(hashsum)
    temp_file = tempfile.NamedTemporaryFile()
    for block in container.download_object_as_stream(obj):
        temp_file.write(block)
    temp_file.seek(0)
    return gzip.GzipFile(fileobj=temp_file, mode='rb')


def _upload_json(container, objname, data):
    s = json.dumps(data, separators=(',',':'))
    container.upload_object_via_stream(s, objname)


def _download_json(container, objname):
    obj = container.get_object(objname)
    s = cStringIO.StringIO()
    for chunk in container.download_object_as_stream(obj):
        s.write(chunk)
    s.seek(0)
    return json.load(s)


_undefined = object()

class _Store(collections.Mapping):
    """
    Abstract data store for LibCloud storage.
    """

    def __init__(self, driver, container_name):
        """
        Constructor.

        ``driver`` is a LibCloud storage driver. ``container_name`` is
        the name of the container to use. If the container does not
        exist it is created.
        """
        self._container = _get_container(driver, container_name)

    def get(self, key, default=_undefined):
        """
        Retrieve data from the store.

        If no entry for the given key exists a ``KeyError`` is raised
        unless ``default`` is provided, in which case that value is
        returned instead.
        """
        try:
            return self[key]
        except KeyError:
            if default is _undefined:
                raise
            return default

    def _get(self, key):
        """
        Internal data retrieval.

        Subclasses need to overwrite this with the actual data
        retrieval code. ``get`` is a simple wrapper around ``_get``
        and just adds the handling of default values.
        """
        raise NotImplementedError()

    def remove(self, key):
        """
        Remove an entry from the store.
        """
        try:
            obj = self._container.get_object(path)
        except libcloud.storage.types.ObjectDoesNotExistError:
            self._container.delete_object(obj)

    def clear(self):
        """
        Remove all entries from the store.
        """
        for obj in self._container.list_objects():
            self._container.delete_object(obj)

    def __getitem__(self, key):
        return self._get(key)

    def __delitem__(self, key):
        return self.remove(key)

    def __iter__(self):
        for obj in self._container.list_objects():
            yield obj.name

    def __len__(self):
        return len(self._container.list_objects())


class JSONStore(_Store):
    """
    Store for JSON data.
    """

    def put(self, key, value):
        """
        Store data.

        ``value`` is anything that the ``json`` module can turn into a
        JSON-encoded string. ``key`` is the name under which the data
        is stored.
        """
        return _upload_json(self._container, key, value)

    def _get(self, key):
        try:
            return _download_json(self._container, key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError('No entry for key "%s".' % key)

    def __setitem__(self, key, value):
        return self.put(key, value)


class BlobStore(collections.Mapping):
    """
    A blob store.

    This blob store allows you to store arbitrary data using a LibCloud
    storage driver. Data blobs are identified by their hash, which is
    computed when data is stored and can then be used to retrieve the
    data at a later point.
    """

    def put(self, data):
        """
        Store content in the blob store.

        ``data`` can either be a string or an open file-like object.
        Its content is stored in the blob store in compressed form and
        the content's hash is returned. The hash can later be used to
        retrieve the data from the blob store.
        """
        return _compress_and_upload(self._container, data)

    def get_file(self, hashsum):
        """
        Retrieve data from the blob store in the form of a file-object.

        Returns data that was previously stored via ``put``. The return
        value is a ``gzip.GzipFile`` instance which behaves like a
        standard Python file object and performs the decompression.
        """
        try:
            return _download_and_decompress(self._container, hashsum)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError('No blob for hashsum "%s".' % hashsum)

    def _get(self, hashsum):
        with self.get_file(hashsum) as gzip_file:
            return gzip_file.read()

    def __setitem__(self, key, value):
        raise TypeError('Indexed writing is not possible. Use "put".')


def local_storage_driver(path):
    """
    Create a local LibCloud storage driver.

    ``path`` is the directory in which the data is stored. It is
    automatically created if it does not exist.

    Returns an instance of
    ``libcloud.storage.drivers.local.LocalStorageDriver``.
    """
    try:
        os.mkdir(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    return libcloud.storage.drivers.local.LocalStorageDriver(path)
