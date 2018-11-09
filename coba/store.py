#!/usr/bin/env python3

import json
import logging
import os
import shutil
import tempfile

from hashfs import HashFS


log = logging.getLogger(__name__)


class Store:
    '''
    An on-disk store for file versions.
    '''
    # Subdirectory for content-addressable storage
    _CAS_DIRNAME = 'content'

    def __init__(self, path):
        '''
        Constructor.

        ``path`` is the base directory of the file store. If it doesn't
        exist it is created.
        '''
        try:
            self.path = path.resolve()
        except FileNotFoundError:
            path.mkdir(parents=True)
            self.path = path.resolve()
            log.debug('Created directory {} for store'.format(self.path))
        else:
            if not self.path.is_dir():
                raise ValueError('{} exists but is not a directory'.format(
                                 self.path))
        self._cas = HashFS(str(self.path / self._CAS_DIRNAME), depth=4,
                           width=1, algorithm='sha1')

    def put(self, path):
        '''
        Put a file into the store.
        '''
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
            # FIXME: Store metadata in database
        finally:
            os.unlink(temp_copy.name)
            log.debug('Removed temporary file {}'.format(temp_copy.name))

