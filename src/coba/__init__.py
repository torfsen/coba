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
Coba main module.
"""

import collections
import datetime
import grp
import json
import os
import pwd
import stat
import time
import warnings

import pathlib

from .config import Configuration
from .stores import BlobStore, local_storage_driver, PathStore
from .utils import make_dirs, normalize_path
from .watch import Service

__version__ = '0.1.0'

__all__ = ['Coba', 'File', 'Revision']


class _JSONEncoder(json.JSONEncoder):
    """
    JSON encoder for file information classes.
    """
    def default(self, obj):
        if isinstance(obj, Revision):
            return obj._to_json()
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

        Do not instantiate this class directly. Use :py:meth:`Coba.file`
        or :py:meth:`Coba.files` instead.
        """
        self._coba = coba
        self.path = normalize_path(path)

    def _object_hook(self, d):
        """
        JSON object hook.
        """
        return Revision(self, **d)

    def get_revisions(self):
        """
        Get the file's revisions.

        Returns a list of the file's revisions as instances of
        :py:class:`Revision`.
        """
        try:
            s = self._coba._info_store[str(self.path)]
        except KeyError:
            return []
        return json.loads(s, object_hook=self._object_hook)

    def is_ignored(self):
        """
        Check if the file is ignored.
        """
        return self._coba.config.is_ignored(self.path)

    def _set_revisions(self, revisions):
        """
        Set the file's revisions.

        ``revisions`` is a list of instances of :py:meth:`Revision`.
        """
        self._coba._info_store[str(self.path)] = json.dumps(
            revisions, separators=(',', ':'), cls=_JSONEncoder)

    def backup(self):
        """
        Create a new revision.

        The current content of the file is stored in the storage. The
        corresponding revision is returned as an instance of
        :py:class:`Revision`.
        """

        with self.path.open('rb') as f:
            hashsum = self._coba._blob_store.put(f)
        try:
            stats = self.path.stat()
            owner_name = pwd.getpwuid(stats.st_uid).pw_name
            group_name = grp.getgrgid(stats.st_gid).gr_name
            revisions = self.get_revisions()
            if revisions:
                id = max(rev.id for rev in revisions) + 1
            else:
                id = 1
            revision = Revision(self, id, time.time(), hashsum, stats.st_mtime,
                                stats.st_uid, owner_name, stats.st_gid,
                                group_name, stat.S_IMODE(stats.st_mode),
                                stats.st_size)
            revisions.append(revision)
            self._set_revisions(revisions)
            return revision
        except:
            # FIXME: We must not do this, since the same content could
            # be referred to by a different revision.
            self._coba._blob_store.remove(hashsum)
            raise

    def filter_revisions(self, hash=None, unique=False):
        """
        Filter revisions.

        By default, all revisions are returned as a list of instances of
        :py:class:`Revision`.

        If ``hash`` is not ``None`` then only revisions whose hash
        starts with the given value are returned.

        If ``unique`` is true then for multiple revisions which have the
        same hash only the most recent one is included in the result.
        """
        revs = self.get_revisions()
        if not revs:
            return []
        if hash:
            revs = [rev for rev in revs if rev.hashsum.startswith(hash)]
        if unique:
            most_recent = collections.OrderedDict()
            for rev in revs:
                most_recent[rev.hashsum] = rev
            revs = most_recent.values()
        return revs

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, str(self.path))


class Revision(object):
    """
    A revision of a file.

    .. py:attribute:: file

        A :py:class:`File` instance describing the revision's source
        location on disk.

    .. py:attribute:: id

        The revision's ID. Two different revisions for the same file
        must have different IDs.

    .. py:attribute:: timestamp

        Timestamp of the moment the revision was created.

    .. py:attribute:: hashsum

        Hashsum of the file's content when the revision was created.

    .. py:attribute:: mtime

        The file's modification time when the revision was created.

    .. py:attribute:: owner_id

        ID of the file's owner when the revision was created.

    .. py:attribute:: owner_name

        Name of the file's owner when the revision was created.

    .. py:attribute:: group_id

        ID of the file's group when the revision was created.

    .. py:attribute:: group_name

        Name of the file's group when the revision was created.

    .. py:attribute:: mode

        Permission bits of the file when the revision was created. This
        is an integer in the format used by :py:func:`os.chmod` and
        :py:func:`os.stat`.

    .. py:attribute:: size

        The file's size in bytes when the revision was created.
    """

    def __init__(self, file, id, timestamp, hashsum, mtime, owner_id,
                 owner_name, group_id, group_name, mode, size):
        """
        Constructor.

        Do not instantiate this class directly. Use
        :py:meth:`File.get_revisions` instead.
        """
        self.id = id
        self.file = file
        self.timestamp = timestamp
        self.hashsum = hashsum
        self.mtime = mtime
        self.owner_id = owner_id
        self.owner_name = owner_name
        self.group_id = group_id
        self.group_name = group_name
        self.mode = mode
        self.size = size

    def restore(self, target=None, content=True, mtime=True, owner=True,
                group=True, mode=True, block_size=2**20):  # flake8: noqa
        """
        Restore the revision.

        The content of the revision is written to disk. By default
        the original filename is used, provide ``target`` to restore
        the revision to a different location. ``target`` can either be
        a string or a ``pathlib.Path`` instance. If ``target`` is an
        (existing) directory then the file's basename is appended to it.

        If ``content`` is false then file content is not restored. Note
        that if ``content`` is false and ``target`` points to a
        non-existing file then the target file is not created at all.

        If ``mtime``  and ``mode`` is false then file's modification
        time and permission bits are not restored, respectively.

        Coba stores both the ID and name of a file's owner and group. By
        default, it is checked whether the current system's name for the
        given ID match the stored name, and the value is only set if
        they do (``owner=True`` and ``group=True``). You can set
        ``owner`` and ``group`` to ``"id"`` or ``"name"`` to only care
        about the stored ID or name. In the case of ``"name"`` nothing
        is done if there is no user/group in the current system with the
        stored name. You can also set ``owner`` and ``group`` to
        ``False`` to disable the restoration of the file's owner and
        group.

        Returns the final target path to which the revision was
        restored.
        """
        target = pathlib.Path(target or self.file.path)
        if target.is_dir():
            target = target.joinpath(self.file.path.name)
        target = normalize_path(target)
        if content:
            self._restore_content(target, block_size)
        elif not target.exists():
            # No need to restore meta-data for a file that doesn't exist
            return target
        if mtime:
            os.utime(str(target), (self.mtime, self.mtime))
        if owner:
            self._restore_owner(target, owner)
        if group:
            self._restore_group(target, group)
        if mode:
            target.chmod(self.mode)
        return target

    def _restore_content(self, target, block_size):
        """
        Restore the revision's content.

        ``target`` is a :py:class:`pathlib.Path` instance.
        """
        with self.file._coba._blob_store.get_file(self.hashsum) as in_file:
            with target.open('wb') as out_file:
                while True:
                    block = in_file.read(block_size)
                    if not block:
                        break
                    out_file.write(block)

    def _restore_owner(self, target, owner):
        """
        Restore the revision's owner.

        ``target`` is a :py:class:`pathlib.Path` instance and ``owner``
        is as for :py:meth:`Revision.restore`.
        """
        if owner is True or owner == "name":
            try:
                uid = pwd.getpwnam(self.owner_name).pw_uid
            except KeyError:
                warnings.warn(('No user for stored owner name "%s" exists, ' +
                              'not restoring owner.') % self.owner_name)
                return
        if owner is True:
            if uid == self.owner_id:
                os.chown(str(target), uid, -1)
            else:
                warnings.warn(('UID %d for stored owner name "%s" differs ' +
                              'from stored UID %d, not restoring owner.') %
                              (uid, self.owner_name, self.owner_id))
                return
        elif owner == "id":
            os.chown(str(target), self.owner_id, -1)
        elif owner == "name":
            os.chown(str(target), uid, -1)
        elif owner:
            raise ValueError('Illegal value for input argument "owner".')

    def _restore_group(self, target, group):
        """
        Restore the revision's group.

        ``target`` is a :py:class:`pathlib.Path` instance and ``group``
        is as for :py:meth:`Revision.restore`.
        """
        if group is True or group == "name":
            try:
                gid = grp.getgrnam(self.group_name).gr_gid
            except KeyError:
                warnings.warn(('No group for stored group name "%s" exists, ' +
                              'not restoring group.') % self.group_name)
                return
        if group is True:
            if gid == self.group_id:
                os.chown(str(target), -1, gid)
            else:
                warnings.warn(('GID %d for stored group name "%s" differs ' +
                              'from stored GID %d, not restoring group.') %
                              (gid, self.group_name, self.group_id))
                return
        elif group == "id":
            os.chown(str(target), -1, self.group_id)
        elif group == "name":
            os.chown(str(target), -1, gid)
        elif group:
            raise ValueError('Illegal value for input argument "group".')

    def __repr__(self):
        p = str(self.file.path)
        d = datetime.datetime.fromtimestamp(self.timestamp).isoformat(' ')
        return "%s(%r, '%s')" % (self.__class__.__name__, p, d)

    def _to_json(self):
        """
        Returns a JSON-serializable view of the revision.
        """
        return {k: v for k, v in self.__dict__.iteritems() if not
                k.startswith('_') and k != 'file'}


class Coba(object):
    """
    Main class of Coba.

    This class assembles the different parts of the Coba system and
    offers a high-level interface for perfoming continuous backups.
    """
    def __init__(self, config=None):
        """
        Constructor.

        ``config`` is a :py:class:`coba.config.Configuration` instance.
        If it is not given the configuration is loaded from its default
        location (``~/.coba/.config.json``) if that file exists.
        Otherwise the default configuration is used.
        """
        self.config = config or Configuration.load()
        make_dirs(self.config.pid_dir)
        driver = local_storage_driver(self.config.storage_dir)
        self._blob_store = BlobStore(driver, 'coba-blobs')
        self._info_store = PathStore(driver, 'coba-info')

        def backup(path):
            self.file(path).backup()

        self.service = Service(backup, self.config)

    def start(self, block=False):
        """
        Start the backup daemon.

        If ``block`` is true then the call blocks until the daemon
        process has started. ``block`` can either be ``True`` (in which
        case it blocks indefinitely) or a timeout in seconds.

        The return value is ``True`` if the daemon process has been
        started and ``False`` otherwise.
        """
        return self.service.start(block)

    def stop(self, block=False):
        """
        Stop the backup daemon.

        If ``block`` is true then the call blocks until the daemon
        process has exited. This may take some time since the daemon
        process will complete its on-going backup activities before
        shutting down. ``block`` can either be ``True`` (in which case
        it blocks indefinitely) or a timeout in seconds.

        The return value is ``True`` if the daemon process has been
        stopped and ``False`` otherwise.
        """
        return self.service.stop(block)

    def kill(self):
        """
        Kill the backup daemon.
        """
        self.service.kill()

    def is_running(self):
        """
        Check if the backup daemon is running.
        """
        return self.service.is_running()

    def get_pid(self):
        """
        Return the backup daemon's PID.

        Returns the PID or ``None`` if the backup daemon is not running.
        """
        return self.service.get_pid()

    def files(self):
        """
        List stored files.

        This generator yields all files in the storage as instances of
        :py:class:`File`.
        """
        for path in self._info_store:
            yield File(self, path)

    def file(self, path):
        """
        Get information about a file.

        Returns an instance of :py:class:`File` for the file with the
        given path.
        """
        return File(self, path)

