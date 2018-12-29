#!/usr/bin/env python3

from pathlib import Path

import pytest

from coba.config import Config, DEFAULT_CONFIG


class TestConfig:
    def test_is_file_ignored_by_path(self):
        '''
        Ignore a file by its path.
        '''
        cfg = Config('x', 1, ['*.foo'])
        assert cfg.is_file_ignored(Path('x.foo'))
        assert not cfg.is_file_ignored(Path('x.bar'))

    def test_is_file_ignored_by_size(self, temp_dir):
        '''
        Ignore a file by its size.
        '''
        cfg = Config('x', 10, [])
        smaller_file = temp_dir / 'small'
        smaller_file.write_text('123456789', encoding='ascii')
        equal_file = temp_dir / 'equal'
        equal_file.write_text('1234567890', encoding='ascii')
        larger_file = temp_dir / 'larger'
        larger_file.write_text('12345678901', encoding='ascii')
        missing_file = temp_dir / 'missing'
        assert not cfg.is_file_ignored(smaller_file)
        assert not cfg.is_file_ignored(equal_file)
        assert cfg.is_file_ignored(larger_file)
        assert not cfg.is_file_ignored(missing_file)

    def test_from_file_defaults(self, temp_dir):
        '''
        Default values when loading a config file.
        '''
        cfg_file = temp_dir / 'coba.yml'

        cfg_file.write_text('store_path: foobar\n')
        cfg = Config.from_file(cfg_file)
        assert cfg.store_path == Path('foobar')
        assert cfg.max_file_size == DEFAULT_CONFIG.max_file_size
        assert cfg.ignores == DEFAULT_CONFIG.ignores

        cfg_file.write_text('max_file_size: 123 k\n')
        cfg = Config.from_file(cfg_file)
        assert cfg.store_path == DEFAULT_CONFIG.store_path
        assert cfg.max_file_size == 125952
        assert cfg.ignores == DEFAULT_CONFIG.ignores

        cfg_file.write_text('ignores:\n  - a\n  - b\n')
        cfg = Config.from_file(cfg_file)
        assert cfg.store_path == DEFAULT_CONFIG.store_path
        assert cfg.max_file_size == DEFAULT_CONFIG.max_file_size
        assert cfg.ignores == ['a', 'b']

    def test_from_file_missing_file(self):
        '''
        Load configuration from a missing file.
        '''
        with pytest.raises(FileNotFoundError):
            Config.from_file(Path('does/not/exist'))
