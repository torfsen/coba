#!/usr/bin/env python

"""
Data stores based on LibCloud storage.
"""

import collections
import cStringIO
import errno
import json
import gzip
import hashlib
import os
import tempfile

import libcloud.storage.types
import libcloud.storage.drivers.local

from .utils import binary_file_iterator, normalize_path


__all__ = [
    'AbstractStore',
    'BlobStore',
    'ChainedTransformer',
    'CompressTransformer',
    'CompressAndHashTransformer',
    'JSONStore',
    'JSONTransformer',
    'local_storage_driver',
    'PathStore',
    'StringStore',
    'Transformer',
    'TransformingStore',
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


def _upload_from_file(container, objname, fobj):
    """
    Upload file content to a LibCloud object.
    """
    fobj.seek(0)
    iterator = binary_file_iterator(fobj)
    container.upload_object_via_stream(iterator, objname)


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


class Transformer(object):
    """
    Base class for key/value transformers.

    A transformer transforms data before it is uploaded to a cloud
    store and inverts the transformation when the data is retrieved
    again.

    During upload, transformers may transform the key, too, while
    during downloads only the value transformation is inverted. This
    allows transformers to provide a key based on the transformed
    content (see, for example, ``CompressAndHashTransformer``).
    """

    def transform(self, key, value):
        """
        Transform a key/value pair.

        Returns the transformed pair.
        """
        return key, value

    def invert(self, value):
        """
        Invert a value transformation.

        Returns the original value.
        """
        return value


class CompressTransformer(Transformer):
    """
    Takes a file and turns it into a compressed file.
    """

    def __init__(self, block_size=2**20):
        super(CompressTransformer, self).__init__()
        self.block_size = block_size

    def transform(self, key, value):
        temp_file = tempfile.TemporaryFile()
        value.seek(0)
        with gzip.GzipFile(filename='', fileobj=temp_file,
                           mode='wb') as gzip_file:
            while True:
                block = value.read(self.block_size)
                if not block:
                    break
                gzip_file.write(block)
        temp_file.seek(0)
        return key, temp_file

    def invert(self, value):
        value.seek(0)
        return gzip.GzipFile(filename='', fileobj=value, mode='rb')


class CompressAndHashTransformer(CompressTransformer):
    """
    Takes a file and turns it into a compressed file. The key is
    replaced by the data's hashsum.
    """

    def transform(self, key, value):
        hasher = hashlib.sha256()
        temp_file = tempfile.TemporaryFile()
        value.seek(0)
        with gzip.GzipFile(filename='', fileobj=temp_file,
                           mode='wb') as gzip_file:
            while True:
                block = value.read(self.block_size)
                if not block:
                    break
                hasher.update(block)
                gzip_file.write(block)
        temp_file.seek(0)
        return hasher.hexdigest(), temp_file


class JSONTransformer(Transformer):
    """
    Takes a Python object and turns it into a JSON-encoded file.
    """

    def transform(self, key, value):
        out_file = cStringIO.StringIO()
        json.dump(value, out_file, separators=(',',':'))
        out_file.seek(0)
        return key, out_file

    def invert(self, value):
        value.seek(0)
        return json.load(value)


class ChainedTransformer(Transformer):
    """
    Chain several transformers into one.
    """

    def __init__(self, transformers):
        """
        Constructor.

        ``transformers`` is a list of ``Transformer`` instances. During
        upload, these are applied in left-to-right fashion. During
        download the transformations are inverted from right to left.

        The caller is responsible for ensuring that the transformers
        are compatiable, i.e. that the output of one transformer is an
        acceptable input for the next one.
        """
        self.transformers = transformers

    def transform(self, key, value):
        for t in self.transformers:
            key, value = t.transform(key, value)
        return key, value

    def invert(self, value):
        for t in reversed(self.transformers):
            value = t.invert(value)
        return value


_undefined = object()

class AbstractStore(collections.Mapping):
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
            obj = self._container.get_object(key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError(key)
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


class StringStore(AbstractStore):
    """
    Store for storing plain strings.
    """

    def put(self, key, value):
        self._container.upload_object_via_stream(value, key)
        return key

    __setitem__ = put

    def _get(self, key):
        try:
            obj = self._container.get_object(key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError(key)
        return ''.join(obj.as_stream())


class TransformingStore(AbstractStore):
    """
    Cloud storage data store with built-in value transformations.

    This class automatically transforms values during up- and download
    based on a ``Transformer`` instance.
    """

    def __init__(self, driver, container_name, transformer):
        """
        Constructor.

        ``transformer`` is an instance of ``Transformer`` which must return
        an open file-like object during the upload transformation.
        """
        super(TransformingStore, self).__init__(driver, container_name)
        self._transformer = transformer

    def _get(self, key):
        """
        Download data from the store.

        The transformation performed during the upload is automatically
        inverted.
        """
        try:
            temp_file = _download_to_temp_file(self._container, key)
        except libcloud.storage.types.ObjectDoesNotExistError:
            raise KeyError(key)
        return self._transformer.invert(temp_file)

    def _put(self, key, value):
        """
        Upload data to the store.

        The key/value pair is automatically transformed. The
        transformed value is stored in the cloud storage using the
        transformed key. The latter is returned to allow for retrieval
        of the data later on.
        """
        key, value = self._transformer.transform(key, value)
        _upload_from_file(self._container, key, value)
        return key


class JSONStore(TransformingStore):
    """
    Store for JSON data.

    Data is transformed into JSON-encoded strings before upload and
    decoded after download.
    """

    def __init__(self, driver, container_name):
        super(JSONStore, self).__init__(driver, container_name,
                                        JSONTransformer())

    def put(self, key, value):
        """
        Store data in the store.

        ``value`` is anything that Python's ``json`` module can encode
        into a JSON string.
        """
        return super(JSONStore, self)._put(key, value)

    __setitem__ = put


class BlobStore(TransformingStore):
    """
    A blob store.

    This blob store allows you to store arbitrary data using a LibCloud
    storage driver. Data blobs are identified by their hash, which is
    computed when data is stored and can then be used to retrieve the
    data at a later point.
    """

    def __init__(self, driver, container_name):
        super(BlobStore, self).__init__(driver, container_name,
                                        CompressAndHashTransformer())

    def put(self, data):
        """
        Store content in the blob store.

        ``data`` can either be a string or an open file-like object.
        Its content is stored in the blob store in compressed form and
        the content's hash is returned. The hash can later be used to
        retrieve the data from the blob store.
        """
        if not hasattr(data, 'read'):
            # Not a file, assume string
            data = cStringIO.StringIO(data)
        return super(BlobStore, self)._put(None, data)

    def get_file(self, hashsum):
        """
        Retrieve data from the blob store in the form of a file-object.

        Returns data that was previously stored via ``put``. The return
        value is a ``gzip.GzipFile`` instance which behaves like a
        standard Python file object and performs the decompression.
        """
        return super(BlobStore, self)._get(hashsum)

    def _get(self, hashsum):
        return super(BlobStore, self)._get(hashsum).read()

    def __setitem__(self, key, value):
        raise TypeError('Indexed writing is not possible. Use "put".')


class PathStore(StringStore):
    """
    Store for storing plain strings with support for paths as keys.

    This is basically a ``StringStore`` but with additional plumbing to
    allow paths to be used as keys.
    """

    def _path2key(self, path):
        """
        Convert a path to a key.
        """
        path = str(normalize_path(path))
        assert path.startswith('/')
        # We need to return the leading slash from the path to fake a
        # relative path. Absolute paths are buggy or not supported in
        # many LibCloud storage drivers.
        return path[1:]

    def _key2path(self, key):
        """
        Convert a key to a path.
        """
        return '/' + key

    def put(self, path, value):
        key = self._path2key(path)
        super(PathStore, self).put(key, value)
        return path

    __setitem__ = put

    def _get(self, path):
        return super(PathStore, self)._get(self._path2key(path))

    def remove(self, path):
        return super(PathStore, self).remove(self._path2key(path))

    def __iter__(self):
        for obj in self._container.list_objects():
            yield self._key2path(obj.name)

