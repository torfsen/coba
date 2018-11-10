#!/usr/bin/env python3

import contextlib
import datetime
import json
import logging
import os
import os.path
from pathlib import Path
import shutil
import tempfile

import hashfs
from sqlalchemy import Column, create_engine, DateTime, Integer, Unicode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


__all__ = ['Store']


log = logging.getLogger(__name__)

_Base = declarative_base()
_Session = sessionmaker()


@contextlib.contextmanager
def _session_scope():
    session = _Session()
    try:
        yield session
    except:
        session.rollback()
        raise
    finally:
        session.close()


class _Version(_Base):
    __tablename__ = 'versions'

    id = Column(Integer, primary_key=True)
    path = Column(Unicode, nullable=False)
    hash = Column(Unicode(40), nullable=False)
    stored_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    def __repr__(self):
        return '<{} id={} path="{}" hash="{}">'.format(self.__class__.__name__,
                                                       self.id, self.path,
                                                       self.hash)


def _make_absolute(p):
    '''
    Make a ``pathlib.Path`` absolute.

    Does not resolve symbolic links.
    '''
    return Path(os.path.normcase(os.path.abspath(str(p))))


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

    def __enter__(self):
        try:
            self.path = self.path.resolve()
        except FileNotFoundError:
            self.path.mkdir(parents=True)
            self.path = self.path.resolve()
            log.debug('Created directory {} for store'.format(self.path))
        else:
            if not self.path.is_dir():
                raise ValueError('{} exists but is not a directory'.format(
                                 self.path))
        self._cas = hashfs.HashFS(str(self.path / 'content'), depth=4,
                                  width=1, algorithm='sha1')
        self._init_db()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._close_db()

    def _init_db(self):
        log.debug('Initializing database')
        url = 'sqlite:///' + str(self.path / 'coba.sqlite')
        self._engine = create_engine(url)
        _Base.metadata.create_all(self._engine, checkfirst=True)
        _Session.configure(bind=self._engine)

    def _close_db(self):
        log.debug('Closing database')
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def put(self, path):
        '''
        Put a file into the store.
        '''
        # First make a temporary copy in case the original file is modified
        # while we're trying to put it into the store
        path = _make_absolute(path)
        temp_copy = tempfile.NamedTemporaryFile(dir=str(self.path), delete=False)
        log.debug('Created temporary file {}'.format(temp_copy.name))
        try:
            temp_copy.close()
            shutil.copy2(str(path), temp_copy.name, follow_symlinks=False)
            log.debug('Created temporary copy {} of {}'.format(temp_copy.name, path))
            address = self._cas.put(temp_copy.name)
            log.debug('Stored content of {} in CAS at {}'.format(path,
                      address.abspath))
            with _session_scope() as session:
                version = _Version(path=str(path), hash=address.id)
                session.add(version)
                session.commit()
                log.debug('Stored new version of {} in row {}'.format(
                          path, version.id))
        finally:
            os.unlink(temp_copy.name)
            log.debug('Removed temporary file {}'.format(temp_copy.name))

