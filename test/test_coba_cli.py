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

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

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

from .utils import TempDirTest


def assert_matches(pattern, string):
    m = re.match(pattern, string)
    if not m:
        raise AssertionError('%r does not match %r.' % (pattern, string))


# Pattern matching a single line of output from `coba revs ...`
_REVS_LINE = r'[xrw-]{10} \w+ \w+ \d+ \d{4}-\d\d-\d\d \d\d:\d\d:\d\d (\w+)\n'

class TestCobaCLI(TempDirTest):
    """
    Tests for ``coba.cli``.
    """
    def teardown(self):
        self.run('kill')
        os.chdir(self.old_dir)
        super(TestCobaCLI, self).teardown()

    def setup(self):
        super(TestCobaCLI, self).setup()
        self.mkdir('watch')
        self.old_dir = os.getcwd()
        os.chdir(self.path('watch'))

    def run(self, *args, **kwargs):
        self.config_args.update(kwargs)
        self.config_args['watched_dirs'] = [self.path('watch')]
        coba.cli._config = Configuration(**self.config_args)
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

    def start(self):
        self.run('start')
        time.sleep(1)

    def test_status_not_running(self):
        code, output = self.run('status')
        eq(output, 'The backup daemon is not running.\n')
        eq(code, 1)

    def test_status_running(self):
        self.start()
        code, output = self.run('status')
        eq(output, 'The backup daemon is running.\n')
        eq(code, 0)

    def test_status_running_verbose(self):
        self.start()
        code, output = self.run('-v', 'status')
        assert_matches('The backup daemon is running.\nDaemon PID is \\d+.\n',
                       output)
        eq(code, 0)

    def test_start_already_running(self):
        self.start()
        code, output = self.run('start')
        assert_matches('Error: Daemon is already running at PID \\d+.\n',
                       output)
        eq(code, 1)

    def test_stop_running(self):
        self.start()
        code, output = self.run('stop')
        time.sleep(1)
        eq(output, '')
        eq(code, 0)

    def test_stop_not_running(self):
        code, output = self.run('stop')
        eq(output, 'Error: Daemon is not running.\n')
        eq(code, 1)

    def test_revs(self):
        self.start()
        code, output = self.run('revs', 'foo')
        eq(output, '')
        eq(code, 0)
        code, output = self.run('-v', 'revs', 'foo')
        assert_matches(r'No revisions for ".*".\n', output)
        eq(code, 0)
        self.write('watch/foo', 'foo')
        time.sleep(1)
        code, output = self.run('revs', 'foo')
        assert_matches(_REVS_LINE, output)
        first_line = output
        eq(code, 0)
        self.write('watch/foo', 'bar')
        time.sleep(1)
        code, output = self.run('revs', 'foo')
        m = re.match(_REVS_LINE + _REVS_LINE, output)
        ok(m)
        eq(code, 0)
        hash = m.groups()[0]
        code, output = self.run('revs', '--hash', hash[:5], 'foo')
        eq(output, first_line)
        eq(code, 0)

    def test_restore(self):
        self.start()
        self.write('watch/foo', 'foo')
        time.sleep(1)
        self.write('watch/foo', 'bar')
        time.sleep(1)
        code, output = self.run('revs', 'foo')
        m = re.match(_REVS_LINE + _REVS_LINE, output)
        ok(m)
        eq(code, 0)
        hash = m.groups()[0]
        code, output = self.run('restore', '--hash', hash[:5], 'foo')
        eq(output, '')
        eq(code, 0)
        eq(self.read('watch/foo'), 'foo')
        self.write('watch/foo', 'bar')
        code, output = self.run('-v', 'restore', '--hash', hash[:5], 'foo')
        assert_matches(r'Restored content of ".*/foo" from revision ".*".',
                       output)
        eq(code, 0)
        eq(self.read('watch/foo'), 'foo')
        code, output = self.run('restore', '--hash', hash[:5], 'foo', 'bar')
        eq(output, '')
        eq(code, 0)
        eq(self.read('watch/bar'), 'foo')
        code, output = self.run('-v', 'restore', '--hash', hash[:5], 'foo',
                                'baz')
        assert_matches(r'Restored content of ".*/foo" from revision ".*" ' +
                       'to ".*/baz".', output)
        eq(code, 0)
        eq(self.read('watch/baz'), 'foo')

    def test_log(self):
        self.start()
        code, output = self.run('log')
        ok(output)
        eq(code, 0)
        code, output = self.run('log', '--lines', 2)
        ok(output)
        eq(len(output.split('\n')), 3)
        eq(code, 0)

