#!/usr/bin/env python3

import contextlib
import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile

import hashfs
from sqlalchemy import Column, create_engine, DateTime, Integer, types, Unicode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .utils import make_path_absolute


__all__ = ['Store', 'Version']


log = logging.getLogger(__name__)


class _PathType(types.TypeDecorator):
    '''
    SQLAlchemy column type for ``pathlib.Path`` instances.

    Stores the instances as ``sqlalchemy.Unicode``.
    '''
    impl = Unicode

    def process_bind_param(self, value, dialect):
        assert isinstance(value, Path)
        return str(value)

    def process_result_value(self, value, dialect):
        return Path(value)

    def copy(self, **kw):
        return self.__class__(self.impl.length)


_Base = declarative_base()


class _Version(_Base):
    '''
    Internal ORM representation of a file version.
    '''
    __tablename__ = 'versions'

    id = Column(Integer, primary_key=True)
    path = Column(_PathType, nullable=False)
    hash = Column(Unicode(40), nullable=False)
    stored_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    def __repr__(self):
        return '<{} id={} path="{}" hash="{}">'.format(self.__class__.__name__,
                                                       self.id, self.path,
                                                       self.hash)


class Version:
    '''
    A version of a file.
    '''
    def __init__(self, _version, store):
        '''
        Private constructor.
        '''
        self._version = _version
        self._store = store

    def __getattr__(self, attr):
        if attr.startswith('_'):
            raise AttributeError(attr)
        return getattr(self._version, attr)

    def restore(self, target_path=None, force=False):
        '''
        Restore this version.

        If ``target_path`` is not given then the version is restored at
        its original location.

        If the target path already exists and is a directory then the
        version's basename is appended to the path. If the path already
        exists and is a file then a ``FileExistsError`` is raised,
        unless ``force`` is true (in which case the existing file is
        overwritten).

        Returns the path at which the version was restored.
        '''
        if target_path:
            target_path = make_path_absolute(target_path)
            if target_path.is_dir():
                target_path = target_path / self.path.name
        else:
            target_path = Path(self.path)
        return self._store._restore(self._version, target_path, force)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        self_dict = {k: v for k, v in self._version.__dict__.items()
                     if not k.startswith('_')}
        other_dict = {k: v for k, v in other._version.__dict__.items()
                      if not k.startswith('_')}
        return self_dict == other_dict

    def __repr__(self):
        return ('<{cls} id={id} path={path} '
                + 'stored_at={stored_at:%Y-%m-%d/%H:%M:%S}>').format(
               cls=self.__class__.__name__, id=self.id, path=self.path,
               stored_at=self.stored_at)


class Store:
    '''
    An on-disk store for file versions.
    '''
    def __init__(self, path):
        '''
        Constructor.

        ``path`` is the base directory of the file store. If it doesn't
        exist it is created.
        '''
        self.path = path
        self._cas = None
        self._engine = None
        self._Session = None

    def __enter__(self):
        try:
            self.path = self.path.resolve()
        except FileNotFoundError:
            self.path.mkdir(parents=True)
            self.path = self.path.resolve()
            log.debug('Created directory {} for store'.format(self.path))
        else:
            if not self.path.is_dir():
                raise FileExistsError('{} exists but is not a directory'.format(
                                     self.path))
        self._cas = hashfs.HashFS(str(self.path / 'content'), depth=4,
                                  width=1, algorithm='sha1')
        self._init_db()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._close_db()

    def _init_db(self):
        '''
        Initialize the database.
        '''
        log.debug('Initializing database')
        url = 'sqlite:///' + str(self.path / 'coba.sqlite')
        self._engine = create_engine(url)
        _Base.metadata.create_all(self._engine, checkfirst=True)
        self._Session = sessionmaker(bind=self._engine)

    def _close_db(self):
        '''
        Dispose the database engine.
        '''
        log.debug('Closing database')
        if self._engine:
            self._engine.dispose()
            self._engine = None

    @contextlib.contextmanager
    def _session_scope(self):
        '''
        Context manager that provides a SQLAlchemy session.

        The session is closed automatically when the context manager
        exists and rolled back in case of an exception.
        '''
        session = self._Session()
        try:
            yield session
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def put(self, path):
        '''
        Put a file into the store.

        ``path`` is the file to be put into the store.

        Returns a ``Version``.
        '''
        path = make_path_absolute(path)
        # First make a temporary copy in case the original file is modified
        # while we're trying to put it into the store
        temp_copy = tempfile.NamedTemporaryFile(dir=str(self.path), delete=False)
        log.debug('Created temporary file {}'.format(temp_copy.name))
        try:
            temp_copy.close()
            shutil.copy2(str(path), temp_copy.name, follow_symlinks=False)
            log.debug('Created temporary copy {} of {}'.format(temp_copy.name, path))
            address = self._cas.put(temp_copy.name)
            log.debug('Stored content of {} in CAS at {}'.format(path,
                      address.abspath))
            with self._session_scope() as session:
                _version = _Version(path=path, hash=address.id)
                session.add(_version)
                session.commit()
                log.debug('Stored new version of {} in row {}'.format(
                          path, _version.id))
                return Version(_version, self)
        finally:
            os.unlink(temp_copy.name)
            log.debug('Removed temporary file {}'.format(temp_copy.name))

    def _restore(self, _version, path, force):
        '''
        Restore a file to a previous version.

        Not intended to be called directly. Use ``Version.restore``
        instead.

        ``_version`` is an instance of ``_Version`` that describes the
        file to be restored.

        ``path`` is the path at which the file is to be restored. Parent
        directories are created as necessary.

        If ``force`` is true then an existing file at ``path`` will be
        replaced. If ``force`` is false then an existing file raises
        a ``FileExistsError``.

        Returns ``path``.
        '''
        if path.exists() and not force:
            raise FileExistsError('"{}" already exists'.format(path))
        address = self._cas.get(_version.hash)
        if not address:
            raise ValueError('Content "{}" not found'.format(_version.hash))
        try:
            path.parent.mkdir(parents=True)
        except FileExistsError:
            pass
        shutil.copyfile(address.abspath, str(path))
        return path

    def get_versions(self, path):
        '''
        Get the stored versions of a file.

        Yields an instance of ``Version`` for each stored version of the
        given file.
        '''
        path = make_path_absolute(path)
        with self._session_scope() as session:
            for _version in session.query(_Version).filter_by(path=path):
                yield Version(_version, self)

    def get_version_at(self, path, at):
        '''
        Get the stored version of a file at a certain point in time.

        ``path`` is the path of the file.

        ``at`` is a ``datetime.datetime`` object.

        Returns the oldest available version before ``at`` as a
        ``Version`` instance, or ``None`` if no version before that
        moment is available.
        '''
        path = make_path_absolute(path)
        with self._session_scope() as session:
            _version = session.query(_Version) \
                              .filter(_Version.path == path) \
                              .filter(_Version.stored_at <= at) \
                              .order_by(_Version.stored_at.desc()) \
                              .first()
            if not _version:
                return None
            return Version(_version, self)

