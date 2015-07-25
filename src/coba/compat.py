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
#
# This module contains code taken from Python 3.4, Copyright © 2001-2015 Python
# Software Foundation; All Rights Reserved. That code is licensed under the PSF
# License, see https://docs.python.org/3/license.html for details.

"""
Python compatibility code.

This module contains code to ease the transition between Python 2 and
Python 3.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from future.builtins import *
from future.builtins.disabled import *

import stat

from backports.pbkdf2 import pbkdf2_hmac


__all__ = ['filemode', 'pbkdf2_hmac']


# The following code is taken from ``stat.py`` of Python 3.4, Copyright
# © 2001-2015 Python Software Foundation; All Rights Reserved. The code
# is licensed under the PSF license, https://docs.python.org/3/license.html.

_filemode_table = (
    ((stat.S_IFLNK,              "l"),
     (stat.S_IFREG,              "-"),
     (stat.S_IFBLK,              "b"),
     (stat.S_IFDIR,              "d"),
     (stat.S_IFCHR,              "c"),
     (stat.S_IFIFO,              "p")),

    ((stat.S_IRUSR,              "r"),),
    ((stat.S_IWUSR,              "w"),),
    ((stat.S_IXUSR|stat.S_ISUID, "s"),
     (stat.S_ISUID,              "S"),
     (stat.S_IXUSR,              "x")),

    ((stat.S_IRGRP,              "r"),),
    ((stat.S_IWGRP,              "w"),),
    ((stat.S_IXGRP|stat.S_ISGID, "s"),
     (stat.S_ISGID,              "S"),
     (stat.S_IXGRP,              "x")),

    ((stat.S_IROTH,              "r"),),
    ((stat.S_IWOTH,              "w"),),
    ((stat.S_IXOTH|stat.S_ISVTX, "t"),
     (stat.S_ISVTX,              "T"),
     (stat.S_IXOTH,              "x"))
)

def filemode(mode):
    """
    Convert a file's mode to a string of the form '-rwxrwxrwx'.
    """
    perm = []
    for table in _filemode_table:
        for bit, char in table:
            if mode & bit == bit:
                perm.append(char)
                break
        else:
            perm.append("-")
    return "".join(perm)

# End of the code taken from ``stat.py`` of Python 3.4.

