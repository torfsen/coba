#!/usr/bin/env python

"""
Storage middle-ware for coba.
"""

import datetime
import json
import time

from .stores import StringStore, BlobStore
from .utils import normalize_path


class _JSONEncoder(json.JSONEncoder):
    """
    JSON encoder for file information classes.
    """
    def default(self, obj):
        if isinstance(obj, Revision):
            return {'timestamp': obj.timestamp, 'hashsum': obj.hashsum}
        return super(_JSONEncoder, self).default(obj)


class File(object):
    """
    A file.

    This class represents a (potentially non-existing) file on the
    local disk. It can be used to create new backups of the file
    or to access the file's revisions.
    """

    def __init__(self, storage, path):
        """
        Constructor.

        Do not instantiate this class directly. Use ``storage.file`` or
        ``storage.files`` instead.
        """
        self._storage = storage
        self.path = normalize_path(path)

    def _object_hook(self, d):
        """
        JSON object hook.
        """
        try:
            return Revision(self, d['timestamp'], d['hashsum'])
        except KeyError:
            return d

    def get_revisions(self):
        """
        Get the file's revisions.

        Returns a list of the file's revisions.
        """
        try:
            s = self._storage._info_store[self.path]
        except KeyError:
            return []
        return json.loads(s, object_hook=self._object_hook)

    def _set_revisions(self, revisions):
        """
        Set the file's revisions.

        ``revisions`` is a list of instances of ``Revision``.
        """
        self._storage._info_store[self.path] = json.dumps(
            revisions, separators=(',', ':'), cls=_JSONEncoder)

    def backup(self):
        """
        Create a new revision.

        The current content of the file is stored in the
        storage. The corresponding revision is returned.
        """
        with open(self.path, 'rb') as f:
            hashsum = self._storage._blob_store.put(f)
        try:
            revisions = self.get_revisions()
            revision = Revision(self, time.time(), hashsum)
            revisions.append(revision)
            self._set_revisions(revisions)
            return revision
        except:
            self._storage._blob_store.remove(hashsum)
            raise

    def __str__(self):
        return self.path

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.path)


class Revision(object):
    """
    A revision of a file.
    """

    def __init__(self, file, timestamp, hashsum):
        """
        Constructor.

        Do not instantiate this class directly. Use
        ``File.get_revisions`` instead.
        """
        self.file = file
        self.timestamp = timestamp
        self.hashsum = hashsum

    def restore(self, path=None, block_size=2**20):
        """
        Restore the revision.

        The content of the revision is written to disk. By default
        the original filename is used, provide ``path`` to restore
        the revision to a different location.
        """
        path = path or self.file.path
        with self.file._storage._blob_store.get_file(self.hashsum) as in_file:
            with open(path, 'wb') as out_file:
                while True:
                    block = in_file.read(block_size)
                    if not block:
                        break
                    out_file.write(block)

    def __repr__(self):
        d = datetime.datetime.fromtimestamp(self.timestamp).isoformat(' ')
        return "%s(%r, '%s')" % (self.__class__.__name__, self.file.path, d)


class _FileInfoStore(StringStore):
    """
    Store for file backup information.

    This is basically a ``StringStore`` but with additional plumbing to
    allow paths to be used as keys.
    """

    def _path2key(self, path):
        """
        Convert a path to a key.
        """
        path = normalize_path(path)
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
        super(_FileInfoStore, self).put(key, value)
        return path

    __setitem__ = put

    def _get(self, path):
        return super(_FileInfoStore, self)._get(self._path2key(path))

    def remove(self, path):
        return super(_FileInfoStore, self).remove(self._path2key(path))

    def __iter__(self):
        for obj in self._container.list_objects():
            yield self._key2path(obj.name)


class Storage(object):
    """
    Storage middle-ware.
    """

    def __init__(self, driver):
        """
        Constructor.

        ``driver`` is a LibCloud storage driver.
        """
        self._blob_store = BlobStore(driver, 'coba-blobs')
        self._info_store = _FileInfoStore(driver, 'coba-info')

    def clear(self):
        """
        Remove all data from the storage.

        This will remove all revisions from the storage.
        """
        self._blob_store.clear()
        self._info_store.clear()

    def files(self):
        """
        List stored files.

        This generator yields all files in the storage.
        """
        for path in self._info_store:
            yield File(self, path)

    def file(self, path):
        """
        Get information about a file.

        Returns an instance of ``File`` for the local file with the
        given path.
        """
        return File(self, path)

