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
Warnings for Coba.
"""

from __future__ import absolute_import

import warnings


__all__ = ['CobaWarning', 'GroupMismatchWarning', 'NoSuchGroupWarning',
           'NoSuchUserWarning', 'UserMismatchWarning', 'warn']


class CobaWarning(UserWarning):
    """
    Base class for Coba-related warnings.
    """
    pass


class GroupMismatchWarning(CobaWarning):
    """
    Issued if there is a mismatch between stored and current group name.
    """
    pass


class NoSuchGroupWarning(CobaWarning):
    """
    Issued if the target group does not exist.
    """
    pass


class UserMismatchWarning(CobaWarning):
    """
    Issued if there is a mismatch between stored and current user name.
    """
    pass


class NoSuchUserWarning(CobaWarning):
    """
    Issued if the target user does not exist.
    """
    pass


def warn(message, category=None, stacklevel=1):
    """
    Issue a warning.

    Works like :py:func:`warnings.warn` but uses :py:class:`CobaWarning`
    as default category.
    """
    warnings.warn(message, category or CobaWarning, stacklevel + 1)

