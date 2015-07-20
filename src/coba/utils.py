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

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import errno
import hashlib
import json
import mmap
import os
import os.path
import re

import pathlib

from .compat import filemode


__all__ = [
    'binary_file_iterator',
    'expand_path',
    'filemode',
    'is_in_dir',
    'make_dirs',
    'match_path',
    'normalize_path',
    'sha1',
    'tail',
    'to_json',
]


def binary_file_iterator(f, block_size=2**20):  # flake8: noqa
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

    ``path`` can either be a string or a :py:class:`pathlib.Path`
    instance.

    The path is normalized using :py:func:`os.path.realpath` and
    :py:func:`os.path.normcase`.

    The return value is a :py:class:`pathlib.Path` instance.
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


def match_path(pattern, path):
    r"""
    Advanced wildcard-based path matching.

    This function is similar to those provided by Python's ``fnmatch``
    module but provides additional features inspired by the git's
    ignore patterns:

    * A single ``*`` matches 0 or more arbitrary characters, except
      ``/``.

    * A ``?`` matches exactly 1 arbitrary character, except ``/``.

    Double asterisks (``**``) are used for matching multiple
    directories:

    * A trailing ``/**`` matches everything in the preceeding
      directory. For example, ``abc/**`` matches ``abc``, ``abc/``, and
      ``abc/def/ghi``.

    * A leading ``**/`` matches in all directories. For example,
      ``**/abc`` matches ``abc``, ``/abc``, ``123/abc``, and
      ``123/456/abc``.

    * ``/**/`` matches one or more directories. For example,
      ``abc/**/def`` matches ``abc/def``, ``abc/123/def``, and
      ``abc/123/456/def`` but not ``abcdef``.

    Any other use of ``**`` raises a ``ValueError``.

    Any special character can be escaped using ``\``: ``\*`` matches
    ``*`` but not ``foo``. To match a single ``\`` use ``\\``.
    """
    i = 0
    parts = []
    suffix = ''
    if pattern.startswith('**/'):
        parts.append('(.*/)?')
        i = 3
    while pattern.endswith('/**'):
        suffix = '(/.*)?'
        pattern = pattern[:-3]
    while i < len(pattern):
        c = pattern[i]
        if pattern[i:i + 4] == '/**/':
            parts.append('/(.*/)?')
            i += 4
        elif c == '*':
            if pattern[i:i + 2] == '**':
                raise ValueError(('Invalid pattern (illegal use of "**" at ' +
                                 'position %d).') % (i + 1))
            parts.append('[^/]*')
            i += 1
        elif c == '?':
            parts.append('[^/]')
            i += 1
        elif c == '\\':
            if i == len(pattern) - 1:
                raise ValueError(('Invalid pattern (illegal use of "\\" at ' +
                                 'position %d).') % (i + 1))
            parts.append(re.escape(pattern[i + 1]))
            i += 2
        else:
            parts.append(re.escape(c))
            i += 1
    regex = ''.join(parts) + suffix + '\Z(?s)'
    return re.match(regex, str(path)) is not None


def make_dirs(path):
    """
    Create directories.

    Like :py:func:`os.makedirs`, but without error if the directory
    exists.
    """
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def expand_path(path):
    """
    Expand ``~`` and environment variables in a path.

    This is a combination of :py:func:`os.path.expanduser` and
    :py:func:`os.path.expandvars`.
    """
    return os.path.expandvars(os.path.expanduser(path))


def sha1(s):
    """
    SHA1 hex digest of a string.
    """
    hasher = hashlib.sha1()
    hasher.update(s)
    return hasher.hexdigest()


def tail(f, n=10):
    """
    Return lines from the end of a file.

    ``f`` is an open file object.

    Returns a list of the last ``n`` lines in the file, or less if the
    file contains less than ``n`` lines. Newline characters are not
    removed.
    """
    lines = []
    try:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    except ValueError:
        # Empty file
        return []
    try:
        j = mm.size()
        while len(lines) < n and j > 0:
            i = mm.rfind('\n', 0, j - 1)
            lines.append(mm[i + 1:j])
            j = i + 1
        lines.reverse()
        return lines
    finally:
        mm.close()


class _JSONEncoder(json.JSONEncoder):
    """
    General JSON encoder.

    This encoder tries to call ``obj._to_json`` on objects it is told
    to encode. It is assumed that this method returns a view of ``obj``
    that can be encoded to JSON by ``json.JSONEncoder``.
    """
    def default(self, obj):
        try:
            return obj._to_json()
        except AttributeError:
            pass
        return super(_JSONEncoder, self).default(obj)


def to_json(obj):
    """
    Compact JSON string representation of an object.

    Any object referenced by ``obj`` which cannot be encoded by
    :py:func:`json.dumps` is expected to provide a ``_to_json`` method
    which returns a view of the object that can be encoded by
    :py:func:`json.dumps`.
    """
    return json.dumps(obj, separators=(',', ':'), cls=_JSONEncoder)

