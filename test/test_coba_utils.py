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
Tests for ``coba.utils``.
"""

import codecs
import contextlib
import os.path
import tempfile

from nose.tools import eq_ as eq, ok_ as ok, raises

from coba.utils import *


#
# Tests for ``match_path``
#

def _check_pattern(pattern, positive, negative):
    for path in positive:
        if not match_path(pattern, path):
            raise AssertionError('%r should match %r but does not.' %
                                 (pattern, path))
    for path in negative:
        if match_path(pattern, path):
            raise AssertionError('%r should not match %r but does.' %
                                 (pattern, path))

def test_match_path_matching():
    for pattern, positive, negative in [
        (
            '*',
            ['', 'foo', 'bar.baz'],
            ['/', '/foo/bar.baz', 'foo/bar.baz']
        ),
        (
            '?',
            ['1', 'f'],
            ['/', '', 'foo', '/foo']
        ),
        (
            '*.l?g',
            ['.log', 'bar.lbg'],
            ['foo/.log', '/bar.lbg']
        ),
        (
            '**/',
            ['', '/', 'a/', '/a/b/', 'a/b/', 'a/b/c/'],
            ['a', 'a/b', '/a/b', 'a/b/c', '/a/b/c']
        ),
        (
            '**/a',
            ['a', '/a', 'b/a', '/c/b/a', 'c/b/a'],
            ['ba']
        ),
        (
            '/**',
            ['', '/', '/a/', '/a/b', '/a/b/c', '/a/b/c/'],
            ['a', 'a/b', 'a/b/c']
        ),
        (
            'a/**',
            ['a', 'a/', 'a/b', 'a/b/', 'a/b/c', 'a/b/c/'],
            ['ab']
        ),
        (
            '/**/',
            ['/', '/a/', '/a/b/', '/a/b/c/'],
            ['', '/a', '/a/b', '/a/b/c', 'a/', 'a/b/', 'a/b/c/', 'a', 'a/b',
             'a/b/c']
        ),
        (
            'a/**/',
            ['a/', 'a/b/', 'a/b/c/'],
            ['a', 'a/b', 'a/b/c', 'ab']
        ),
        (
            '/**/a',
            ['/a', '/b/a', '/c/b/a'],
            ['a', 'b/a', 'c/b/a', 'ba']
        ),
        (
            'a/**/b',
            ['a/b', 'a/c/b', 'a/c/d/b'],
            ['ab']
        ),
    ]:
        yield _check_pattern, pattern, positive, negative

def test_match_path_escaping():
    for pattern, positive, negative in [
        (r'\*', ['*'], ['', 'foo']),
        (r'\?', ['?'], ['a']),
        (r'a/\**/b', ['a/*/b', 'a/*x/b', 'a/**/b'], ['a/x*/b', 'a/1/2/b']),
        (r'a/*\*/b', ['a/*/b', 'a/x*/b', 'a/**/b'], ['a/*x/b', 'a/1/2/b']),
        (r'*\*/a', ['*/a', 'x*/a', '**/a'], ['*x/a', '1/2/a']),
        (r'\**/a', ['*/a', '*x/a', '**/a'], ['x*/a', '1/2/a']),
        (r'a/*\*', ['a/*', 'a/x*', 'a/**'], ['a/*x', 'a/1/2']),
        (r'a/\**', ['a/*', 'a/*x', 'a/**'], ['a/x*', 'a/1/2']),
        (r'a\\*', ['a\\', 'a\\b'], []),
    ]:
        yield _check_pattern, pattern, positive, negative

def test_match_path_invalid_patterns():
    @raises(ValueError)
    def check(pattern):
        match_path(pattern, 'foo')
    for pattern in '**foo foo** foo/**bar foo**/bar foo**bar bar\\'.split():
        yield check, pattern


#
# Tests for ``tail``
#

@contextlib.contextmanager
def temp_file(content=''):
    """
    Context manager that creates a temporary file with given content.

    The file is removed once the content manager exits.
    """
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    try:
        with codecs.open(f.name, 'w+', encoding='utf8') as g:
            g.write(content)
            g.seek(0)
            yield g
    finally:
        os.unlink(f.name)


def test_tail():
    def check(content, expected):
        with temp_file(content) as f:
            eq(tail(f, 3), expected)

    for content, expected in [
        ('', []),
        ('\n', ['\n']),
        ('foobar', ['foobar']),
        ('foobar\n', ['foobar\n']),
        ('foo\nbar', ['foo\n', 'bar']),
        ('foo\nbar\n', ['foo\n', 'bar\n']),
        ('a\nb\nc\nd', ['b\n', 'c\n', 'd']),
        ('a\nb\nc\nd\n', ['b\n', 'c\n', 'd\n']),
    ]:
        yield check, content, expected

