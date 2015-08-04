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

import codecs
import collections
import datetime
import grp
import os
import pwd
import stat
import time

import pathlib

from .config import Configuration
from .crypto import CryptoError, CryptoProvider
from .utils import make_dirs, normalize_path, sha1, tail, to_json
from .watch import Service
from .warnings import (GroupMismatchWarning, NoSuchGroupWarning,
                       NoSuchUserWarning, UserMismatchWarning, warn)

__version__ = '0.1.0'

__all__ = ['Coba', 'File', 'Revision']


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

    def get_revisions(self):
        """
        Get the file's revisions.

        Returns a list of the file's revisions.
        """
        return self._coba.store.get_revisions(self.path)

    def is_ignored(self):
        """
        Check if the file is ignored.
        """
        return self._coba.config.is_ignored(self.path)

    def backup(self):
        """
        Create a new revision.

        The current content of the file is stored and the corresponding
        revision is returned as an instance of :py:class:`Revision`.
        """
        with self.path.open('rb') as f:
            content_hash = self._coba.store.put_content(f)
        stats = self.path.stat()
        return self._coba.store.append_revision(
            path=self.path,
            timestamp=time.time(),
            content_hash=content_hash,
            mtime=stats.st_mtime,
            user_id=stats.st_uid,
            user_name=pwd.getpwuid(stats.st_uid).pw_name,
            group_id=stats.st_gid,
            group_name=grp.getgrgid(stats.st_gid).gr_name,
            mode=stat.S_IMODE(stats.st_mode),
            size=stats.st_size)

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
            revs = [rev for rev in revs if rev.get_hash().startswith(hash)]
        if unique:
            most_recent = collections.OrderedDict()
            for rev in revs:
                most_recent[rev.get_hash()] = rev
            revs = most_recent.values()
        return revs

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, str(self.path))


class Revision(object):
    """
    A revision of a file.

    .. py:attribute:: store

        The :py:class:`Store` instance which contains the
        revision.

    .. py:attribute:: path

        A :py:class:`pathlib.Path` instance describing the revision's
        source location on disk.

    .. py:attribute:: id

        The revision's ID. Two different revisions for the same file
        must have different IDs.

    .. py:attribute:: timestamp

        Timestamp of the moment the revision was created.

    .. py:attribute:: content_hash

        Hashsum of the file's content when the revision was created.

    .. py:attribute:: mtime

        The file's modification time when the revision was created.

    .. py:attribute:: user_id

        ID of the user owning the file when the revision was created.

    .. py:attribute:: user_name

        Name of the user owning the file when the revision was created.

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

    def __init__(self, store, path, timestamp, content_hash, mtime, user_id,
                 user_name, group_id, group_name, mode, size):
        """
        Constructor.

        Do not instantiate this class directly. Use
        :py:meth:`File.get_revisions` instead.
        """
        self.store = store
        self.path = normalize_path(path)
        self.timestamp = timestamp
        self.content_hash = content_hash
        self.mtime = mtime
        self.user_id = user_id
        self.user_name = user_name
        self.group_id = group_id
        self.group_name = group_name
        self.mode = mode
        self.size = size

    def restore(self, target=None, content=True, mtime=True, user=True,
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

        Coba stores both the ID and name of a file's user and group. By
        default (``user=True`` and ``group=True``) it is checked whether
        the current system's name for the given ID matches the stored
        name, and the value is only set if they do. Otherwise a
        :py:class:`coba.warnings.GroupMismatchWarning` or a
        :py:class:`coba.warnings.UserMismatchWarning` is issued. You can
        set ``user`` and ``group`` to ``"id"`` or ``"name"`` to only
        care about the stored ID or name. In the case of ``"name"`` a
        :py:class:`coba.warnings.NoSuchUserWarning` or
        :py:class:`coba.warnings.NoSuchGroupWarning` is issued if there
        is no user/group in the current system with the stored name and
        the file's user is not changed. In the case of ``"id"`` the
        user/group is set to that ID even if there's currently no
        registered user/group for it. You can also set ``user`` and
        ``group`` to ``False`` to disable the restoration of the file's
        user and group.

        Returns the final target path to which the revision was
        restored.
        """
        target = pathlib.Path(target or self.path)
        if target.is_dir():
            target = target.joinpath(self.path.name)
        target = normalize_path(target)
        if content:
            self._restore_content(target, block_size)
        elif not target.exists():
            # No need to restore meta-data for a file that doesn't exist
            return target
        if mtime:
            os.utime(str(target), (self.mtime, self.mtime))
        if user:
            self._restore_user(target, user)
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
        with self.store.get_content(self.content_hash) as in_file:
            with target.open('wb') as out_file:
                while True:
                    block = in_file.read(block_size)
                    if not block:
                        break
                    out_file.write(block)

    def _restore_user(self, target, user):
        """
        Restore the revision's user.

        ``target`` is a :py:class:`pathlib.Path` instance and ``user``
        is as for :py:meth:`Revision.restore`.
        """
        if user is True or user == "name":
            try:
                uid = pwd.getpwnam(self.user_name).pw_uid
            except KeyError:
                warn(('No user for stored user name "%s" exists, ' +
                     'not restoring user.') % self.user_name,
                     NoSuchUserWarning)
                return
        if user is True:
            if uid == self.user_id:
                os.chown(str(target), uid, -1)
            else:
                warn(('UID %d for stored user name "%s" differs from ' +
                     'stored UID %d, not restoring user.') % (uid,
                     self.user_name, self.user_id), UserMismatchWarning)
                return
        elif user == "id":
            os.chown(str(target), self.user_id, -1)
        elif user == "name":
            os.chown(str(target), uid, -1)
        elif user:
            raise ValueError('Illegal value for input argument "user".')

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
                warn(('No group for stored group name "%s" exists, ' +
                     'not restoring group.') % self.group_name,
                     NoSuchGroupWarning)
                return
        if group is True:
            if gid == self.group_id:
                os.chown(str(target), -1, gid)
            else:
                warn(('GID %d for stored group name "%s" differs from ' +
                     'stored GID %d, not restoring group.') % (gid,
                     self.group_name, self.group_id), GroupMismatchWarning)
                return
        elif group == "id":
            os.chown(str(target), -1, self.group_id)
        elif group == "name":
            os.chown(str(target), -1, gid)
        elif group:
            raise ValueError('Illegal value for input argument "group".')

    def __repr__(self):
        p = str(self.path)
        d = datetime.datetime.fromtimestamp(self.timestamp).isoformat(' ')
        return "%s(%r, '%s')" % (self.__class__.__name__, p, d)

    def _to_json(self):
        """
        Returns a JSON-serializable view of the revision.
        """
        return collections.OrderedDict((k, self.__dict__[k]) for k in
                                       sorted(self.__dict__) if k not in
                                       ('path', 'store'))

    def get_hash(self):
        """
        Hash which can be used to identify the revision.

        The hash uniquely identifies the revision among all revisions of
        the same file.
        """
        return sha1(to_json(self))

    def __eq__(self, other):
        """
        Two revisions are considered equal if all of their members except
        ``store`` are equal.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        for k, v in self.__dict__.iteritems():
            if k != 'store' and v != getattr(other, k):
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(tuple(sorted((k, v) for k, v in self.__dict__.iteritems()
                    if k != 'store')))


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
        from .storage import local_storage_driver, Store
        self.config = config or Configuration.load()
        make_dirs(self.config.log_dir)
        make_dirs(self.config.pid_dir)
        driver = local_storage_driver(self.config.storage_dir)
        crypto_provider = CryptoProvider(self.config.encryption_key,
                                         self.config.key_dir)
        if self.config.encryption_key:
            try:
                crypto_provider.test()
            except CryptoError as e:
                raise CryptoError('Encryption is enabled but crypto self-' +
                                  'test failed: %s' % e)
        self.store = Store(driver, 'coba', crypto_provider)

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

    def file(self, path):
        """
        Get information about a file.

        Returns an instance of :py:class:`File` for the file with the
        given path.
        """
        return File(self, path)

    def get_log(self, lines=10):
        """
        Get the latest log messages from the backup daemon.

        Returns the latest ``lines`` log messages issued by Coba's
        backup daemon. If the log file contains less than ``lines``
        lines all of its lines are returned.
        """
        try:
            with codecs.open(self.config.log_file, encoding='utf8') as f:
                return ''.join(tail(f, lines))
        except IOError as e:
            if e.errno == errno.ENOENT:
                # Log file does not exist
                return ''
            raise

