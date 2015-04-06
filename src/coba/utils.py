#!/usr/bin/env python

"""
Various utilities.
"""

import os.path

import pathlib


__all__ = ['binary_file_iterator', 'is_in_dir', 'normalize_path']


def binary_file_iterator(f, block_size=2**20):
    """
    Generator for iterating over binary files in blocks.

    ``f`` is a file opened in binary mode. The generator reads blocks
    from the file, where ``block_size`` is the maximum block size.
    """
    while True:
        block = f.read(block_size)
        if not block:
            return
        yield block


def normalize_path(path):
    """
    Normalize file path.

    ``path`` can either be a string or a ``pathlib.Path`` instance.

    The return value is a ``Path`` instance.
    """
    return pathlib.Path(os.path.normcase(os.path.realpath(str(path))))


def is_in_dir(candidate, parent):
    """
    Check if a path is inside a directory.

    ``candidate`` is a path to a file or directory and ``parent`` is
    a directory path. If ``candidate`` is within ``parent`` the function
    returns ``True``, otherwise it returns ``False``.

    Note that the inclusion check is strict, i.e. if
    ``candidate == parent`` then the function returns ``False``.
    """
    return pathlib.Path(parent) in pathlib.Path(candidate).parents
