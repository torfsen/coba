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
Common utilities for testing.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from future.builtins import *
from future.builtins.disabled import *

import errno
import inspect
import io
import functools
import os
import os.path
import shutil
import stat
import sys
import tempfile
import time

from nose.plugins.skip import SkipTest
from nose_parameterized import parameterized as _parameterized


def _print_logfile_on_error(fun):
    """
    Decorator that prints log file contents on error.

    This is a hack to display the backup daemon's log files when a test
    fails. The problem is that the backup daemon runs in a separate
    process, so its log messages are not captures by nose's logcapture
    plugin. We therefore print them "manually" when a test fails.

    The decorator is applied automagically in
    ``TempDirTest.__getattribute__``.
    """
    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except SkipTest:
            raise
        except Exception:
            exc_info = sys.exc_info()
            log_dir = fun.__self__.config_args['log_dir']
            log_file = os.path.join(log_dir, 'coba.log')
            print('\n===== START OF LOG FILE CONTENTS =====')
            try:
                with io.open(log_file, 'r', encoding='utf8') as f:
                    print(f.read())
            except IOError as e:
                pass
            print('===== END OF LOG FILE CONTENTS =====\n')
            raise exc_info[1].with_traceback(exc_info[2])
    return wrapper


class TempDirTest(object):
    """
    Base class tests in a temporary directory.
    """

    def __getattribute__(self, name):
        # Wrap test cases with `_print_logfile_on_error`
        getattribute = super(TempDirTest, self).__getattribute__
        attr = getattribute(name)
        if name.startswith('test_') and inspect.ismethod(attr):
            attr = _print_logfile_on_error(attr)
        return attr

    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_args = {
            'storage_dir': self.path('storage'),
            'idle_wait_time': 0,
            'pid_dir': self.temp_dir,
            'watched_dirs': [],
            'log_dir': self.path('logs'),
        }

    def teardown(self):
        for root, filenames, dirnames in os.walk(self.temp_dir):
            for filename in filenames:
                fullname = os.path.join(root, filename)
                os.chmod(fullname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        shutil.rmtree(self.temp_dir)

    def path(self, p):
        return os.path.join(self.temp_dir, p)

    def mkdir(self, path):
        path = self.path(path)
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        return path

    def write(self, path, content=''):
        path = self.path(path)
        self.mkdir(os.path.dirname(path))
        with io.open(path, 'w', encoding='utf8') as f:
            f.write(content)
        return content

    def read(self, path):
        path = self.path(path)
        with io.open(path, 'r', encoding='utf8') as f:
            return f.read()

    def move(self, src, target):
        src = self.path(src)
        target = self.path(target)
        os.rename(src, target)

    def set_mtime(self, path, mtime):
        os.utime(self.path(path), (mtime, mtime))

    def get_mtime(self, path):
        return os.path.getmtime(self.path(path))

    def get_mode(self, path):
        return stat.S_IMODE(os.stat(self.path(path)).st_mode)

    def set_mode(self, path, mode):
        os.chmod(self.path(path), mode)

    def wait(self, seconds=2):
        time.sleep(seconds)

    def get_group(self, path):
        return os.stat(self.path(path)).st_gid

    def get_user(self, path):
        return os.stat(self.path(path)).st_uid


def parameterized(*pargs, **pkwargs):
    """
    Like ``nose_parameterized.parameterized`` but adds params to doc strings.

    See https://github.com/wolever/nose-parameterized/issues/27.
    """
    def decorator(f):
        f = _parameterized(*pargs, **pkwargs)(f)
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            for case in f(*args, **kwargs):
                if f.__doc__:
                    wrapper.__doc__ = f.__doc__.strip() + ' %r' % (case[1:],)
                yield case
        return wrapper
    return decorator

