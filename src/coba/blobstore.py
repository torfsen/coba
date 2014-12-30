#!/usr/bin/env python

"""
A blob store based on LibCloud storage.
"""

import collections
import cStringIO
import errno
import gzip
import hashlib
import os
import tempfile

import libcloud.storage.drivers.local
import libcloud.storage.types


__all__ = ['BlobStore', 'local_storage_driver']


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


_undefined = object()


class BlobStore(collections.Mapping):
    """
    A blob store.

    This blob store allows you to store arbitrary data using a LibCloud
    storage driver. Data blobs are identified by their hash, which is
    computed when data is stored and can then be used to retrieve the
    data at a later point.
    """

    _CONTAINER = 'coba-blobs'

    def __init__(self, driver):
        """
        Constructor.

        ``driver`` is a ``libcloud.storage.base.StorageDriver``.
        """
        self._container = _get_container(driver, self._CONTAINER)

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

    def get(self, hashsum, default=_undefined):
        """
        Retrieve data from the blob store.

        Returns data that was previously stored via ``put``.
        ``hashsum`` is the data's hash as returned by ``put``.

        If there is no data stored for the given hash then ``KeyError``
        is raised, unless ``default`` is set in which case that value
        is returned instead.

        ``bs.get(h)`` is equivalent to ``bs[h]``.
        """
        try:
            with self.get_file(hashsum) as gzip_file:
                return gzip_file.read()
        except KeyError:
                if default is _undefined:
                    raise
                return default

    def __getitem__(self, hashsum):
        return self.get(hashsum)

    def __delitem__(self, hashsum):
        return self.remove(hashsum)

    def __setitem__(self, key, value):
        raise TypeError('Indexed writing is not possible. Use "put".')

    def __iter__(self):
        for obj in self._container.list_objects():
            yield obj.name

    def __len__(self):
        return len(self._container.list_objects())

    def clear(self):
        """
        Remove all entries.
        """
        for obj in self._container.list_objects():
            self._container.delete_object(obj)

    def remove(self, hashsum):
        """
        Remove an entry.

        Removes the entry with the given hash. ``bs.remove(h)`` is
        equivalent to ``del bs[h]``.
        """
        obj = self._container.get_object(hashsum)
        self._container.delete_object(obj)


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
