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
