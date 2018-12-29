#!/usr/bin/env python3

from pathlib import Path

import pathspec
import yaml

from .utils import parse_file_size


class Config:
    def __init__(self, store_path, max_file_size, ignores):
        '''
        Constructor.

        ``store_path`` is a ``pathlib.Path`` containing the directory of
        the store.

        ``max_file_size`` is the maximum size of a file in bytes (larger
        files are ignored).

        ``ignores`` is a list of pattern strings describing which paths
        to ignore. Their syntax and semantics are those of
        ``.gitignore`` files.
        '''
        self.store_path = store_path
        self.max_file_size = max_file_size
        self.ignores = ignores
        self._pathspec = pathspec.PathSpec.from_lines('gitwildmatch', ignores)

    @classmethod
    def from_file(cls, path):
        '''
        Load a configuration from a YAML file.
        '''
        y = yaml.safe_load(path.read_text(encoding='utf-8'))
        try:
            store_path = Path(y['store_path'])
        except KeyError:
            store_path = DEFAULT_CONFIG.store_path
        ignores = y.get('ignores', DEFAULT_CONFIG.ignores)
        try:
            max_file_size = parse_file_size(y['max_file_size'])
        except KeyError:
            max_file_size = DEFAULT_CONFIG.max_file_size
        return cls(store_path, max_file_size, ignores)

    def is_file_ignored(self, path):
        '''
        Check if a file is ignored.

        If the file does not exist its size is assumed to be 0.
        '''
        if self._pathspec.match_file(str(path)):
            return True
        try:
            file_size = path.stat().st_size
        except FileNotFoundError:
            file_size = 0
        return file_size > self.max_file_size


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / 'default_config.yml'
DEFAULT_CONFIG = Config('', 0, [])
DEFAULT_CONFIG = Config.from_file(DEFAULT_CONFIG_PATH)

