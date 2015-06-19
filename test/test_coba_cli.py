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
Tests for ``coba.cli``.
"""

import os
import os.path
import re
import shutil
import stat
import tempfile
import time

from click.testing import CliRunner, Result
from nose.tools import eq_ as eq, ok_ as ok

from coba import Coba
import coba.cli
from coba.config import Configuration
from coba.utils import sha1


def assert_matches(pattern, string):
    m = re.match(pattern, string)
    if not m:
        raise AssertionError('%r does not match %r.' % (pattern, string))


class TestCobaCLI(object):
    """
    Tests for ``coba.cli``.
    """
    def path(self, p):
        return os.path.join(self.temp_dir, p)

    def setup(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown(self):
        self.run('kill')
        for root, filenames, dirnames in os.walk(self.temp_dir):
            for filename in filenames:
                fullname = os.path.join(root, filename)
                os.chmod(fullname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        shutil.rmtree(self.temp_dir)

    def run(self, *args, **kwargs):
        config_args = {
            'storage_dir': self.path('storage'),
            'idle_wait_time': 0,
            'pid_dir': self.temp_dir,
            'watched_dirs': [self.path('watch')],
            'log_dir': self.path('logs'),
        }
        config_args.update(kwargs)
        coba.cli._config = Configuration(**config_args)
        runner = CliRunner()
        result = runner.invoke(coba.cli.main, args)
        # Fix for Click issue #362
        exit_code, output = result.exit_code, result.output
        try:
            if exit_code != int(exit_code):
                raise ValueError
        except ValueError:
            output += exit_code + '\n'
            exit_code = 1
        return exit_code, output

    def test_status_not_running(self):
        code, output = self.run('status')
        eq(code, 1)
        eq(output, 'The backup daemon is not running.\n')

    def test_status_running(self):
        self.run('start')
        time.sleep(1)
        code, output = self.run('status')
        eq(code, 0)
        eq(output, 'The backup daemon is running.\n')

    def test_status_running_verbose(self):
        self.run('start')
        time.sleep(1)
        code, output = self.run('-v', 'status')
        eq(code, 0)
        assert_matches('The backup daemon is running.\nDaemon PID is \\d+.\n',
                       output)

    def test_start_already_running(self):
        self.run('start')
        time.sleep(1)
        code, output = self.run('start')
        eq(code, 1)
        assert_matches('Error: Daemon is already running at PID \\d+.\n',
                       output)

