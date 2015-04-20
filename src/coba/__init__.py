#!/usr/bin/env python

"""
Continuous backups.
"""

import datetime
import errno
import json
import os
import threading
import time

import libcloud.storage.drivers.local
import pathlib

from .stores import PathStore, BlobStore
from .utils import normalize_path
from .watch import Service


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

    def __init__(self, coba, path):
        """
        Constructor.

        Do not instantiate this class directly. Use ``Coba.file`` or
        ``Coba.files`` instead.
        """
        self._coba = coba
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
            s = self._coba._info_store[str(self.path)]
        except KeyError:
            return []
        return json.loads(s, object_hook=self._object_hook)

    def _set_revisions(self, revisions):
        """
        Set the file's revisions.

        ``revisions`` is a list of instances of ``Revision``.
        """
        self._coba._info_store[str(self.path)] = json.dumps(
            revisions, separators=(',', ':'), cls=_JSONEncoder)

    def backup(self):
        """
        Create a new revision.

        The current content of the file is stored in the
        storage. The corresponding revision is returned.
        """
        print 'Performing backup of "%s".' % self.path
        with self.path.open('rb') as f:
            hashsum = self._coba._blob_store.put(f)
        try:
            revisions = self.get_revisions()
            revision = Revision(self, time.time(), hashsum)
            revisions.append(revision)
            self._set_revisions(revisions)
            return revision
        except:
            self._coba._blob_store.remove(hashsum)
            raise

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, str(self.path))


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
        the revision to a different location. ``path`` can either be
        a string or a ``pathlib.Path`` instance.
        """
        path = pathlib.Path(path or self.file.path)
        with self.file._coba._blob_store.get_file(self.hashsum) as in_file:
            with path.open('wb') as out_file:
                while True:
                    block = in_file.read(block_size)
                    if not block:
                        break
                    out_file.write(block)

    def __repr__(self):
        p = str(self.file.path)
        d = datetime.datetime.fromtimestamp(self.timestamp).isoformat(' ')
        return "%s(%r, '%s')" % (self.__class__.__name__, p, d)


class Coba(object):
    """
    Main class of coba.

    This class assembles the different parts of the coba systems and
    offers a high-level interface for perfoming continuous backups.
    """

    def __init__(self, driver, watched_dirs=None):
        """
        Constructor.

        ``driver`` is a LibCloud storage driver and ``watched_dirs`` is
        a list of directories to be put under continuous backup. The
        directories must be disjoint, i.e. no directory should contain
        an other one.
        """
        self._blob_store = BlobStore(driver, 'coba-blobs')
        self._info_store = PathStore(driver, 'coba-info')
        self.watched_dirs = [pathlib.Path(d) for d in (watched_dirs or ['.'])]
        self.idle_wait_time = 5
        self.service = Service(self)

    def start(self):
        """
        Start the backup daemon.
        """
        self.service.start()

    def stop(self):
        """
        Stop the backup daemon.
        """
        self.service.stop()

    def kill(self):
        """
        Kill the backup daemon.
        """
        self.service.kill()

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
