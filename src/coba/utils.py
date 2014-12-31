#!/usr/bin/env python

"""
Various utilities.
"""

import os.path


__all__ = ['binary_file_iterator', 'normalize_path']


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
    """
    return os.path.normcase(os.path.realpath(path))
