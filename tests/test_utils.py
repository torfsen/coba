#!/usr/bin/env python3

import os
from pathlib import Path

from coba.utils import make_path_absolute

from .conftest import working_dir


class TestMakePathAbsolute:
    def test_absolute_path(self):
        '''
        Make an absolute path absolute.
        '''
        path = Path('/foo/bar/baz')
        assert make_path_absolute(path) == path

    def test_relative_path(self, temp_dir):
        '''
        Make a relative path absolute.
        '''
        with working_dir(temp_dir):
            assert make_path_absolute('foo') == temp_dir / 'foo'

    def test_normalize_path(self):
        '''
        Normalization of ``..`` and ``.``.
        '''
        assert make_path_absolute('/a/../b/./d/e/.././../f') == Path('/b/f')

    def test_path_with_links(self, temp_dir):
        '''
        Make a path with links absolute.
        '''
        (temp_dir / 'a' / 'b' / 'c').mkdir(parents=True)
        os.symlink('a/b', str(temp_dir / 'x'))
        (temp_dir / 'a/b/c/d').touch()
        os.symlink('d', str(temp_dir / 'a/b/c/y'))
        with working_dir(temp_dir):
            assert make_path_absolute('x/c/y') == temp_dir / 'x/c/y'

