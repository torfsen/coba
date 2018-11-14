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


    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        self_dict = {k: v for k, v in self._version.__dict__.items()
                     if not k.startswith('_')}
        other_dict = {k: v for k, v in other._version.__dict__.items()
                      if not k.startswith('_')}
        return self_dict == other_dict


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

    def get_versions(self, path):
        '''
        Get the stored versions of file.

        Yields an instance of ``Version`` for each stored version of the
        given file.
        '''
        path = make_path_absolute(path)
        with self._session_scope() as session:
            for _version in session.query(_Version).filter_by(path=path):
                yield Version(_version, self)

