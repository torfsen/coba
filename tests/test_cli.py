#!/usr/bin/env python3

# Copyright (c) 2018 Florian Brucker (mail@florianbrucker.de).
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

import datetime

from click.testing import CliRunner
import pytest

from coba.cli import coba
from coba.utils import utc_to_local

from .conftest import working_dir


# TODO: These tests should use a mock store instead of a real one

def run(args, expect='success'):
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(coba, args, catch_exceptions=False)
    if expect == 'success':
        assert result.exit_code == 0
    elif expect == 'failure':
        assert result.exit_code != 0
    return result


def assert_failure(args, msg=None):
    result = run(args, expect='failure')
    if msg:
        assert msg.lower() in result.stderr.lower()
    assert not result.stdout


def check_missing_argument(args):
    assert_failure(args, 'missing argument')


class TestWatch:
    def test_no_argument(self):
        '''
        Run ``watch`` without specifying a directory.
        '''
        check_missing_argument(['watch'])

    def test_nonexisting_path(self):
        '''
        Run ``watch`` on a path that doesn't exist.
        '''
        result = run(['watch', '/does/not/exist'], expect='failure')

    def test_not_a_directory(self, temp_dir):
        '''
        Run ``watch`` on an existing path that is not a directory.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.touch()
        result = run(['watch', str(test_file)], expect='failure')

    # TODO: Test backup operation once config options can be properly set


class TestVersions:
    def test_no_argument(self):
        '''
        Run ``versions`` without any arguments.
        '''
        check_missing_argument(['versions'])

    def test_no_versions(self, temp_dir):
        '''
        Run ``versions`` on a file without versions.
        '''
        result = run(['--store', str(temp_dir), 'versions', '/does/not/exist'])
        assert not result.stdout

    def test_one_and_multiple_versions(self, store, temp_dir):
        '''
        Run ``versions`` on a file with one and multiple versions.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.touch()
        versions = []
        for i in range(5):
            versions.append(store.put(test_file))
            expected_output = ''.join('{:%Y-%m-%d %H:%M:%S}\n'.format(
                                      utc_to_local(v.stored_at))
                                      for v in versions)
            # Test with absolute path
            result = run(['--store', str(store.path), 'versions', str(test_file)])
            assert result.stdout == expected_output
            # Test with relative path
            with working_dir(temp_dir):
                result = run(['--store', str(store.path), 'versions', 'test.txt'])
                assert result.stdout == expected_output


class TestRestore:
    def test_not_enough_arguments(self):
        '''
        Run ``restore`` with too few arguments.
        '''
        check_missing_argument(['restore'])
        check_missing_argument(['restore', 'one'])

    def test_invalid_datetime(self):
        '''
        Run ``restore`` with an invalid datetime.
        '''
        assert_failure(['restore', 'foobar', 'foobar'], 'unknown date/time format')

    def test_no_version(self):
        '''
        Run ``restore`` for a datetime without a version.
        '''
        assert_failure(['restore', '2018-01-01', 'foobar'], 'no version in store')

    def test_original_path(self, store, temp_dir):
        '''
        ``restore`` a version to its original path.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        store.put(test_file)
        test_file.unlink()
        when = datetime.datetime.now() + datetime.timedelta(minutes=1)
        result = run(['--store', str(store.path),
                      'restore',
                      '{:%Y-%m-%d %H:%M:%S}'.format(when),
                      str(test_file)])
        assert test_file.read_text() == 'foo'

    def test_custom_path(self, store, temp_dir):
        '''
        ``restore`` a version to a different path.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        store.put(test_file)
        test_file.write_text('bar')
        target_file = temp_dir / 'target.txt'
        when = datetime.datetime.now() + datetime.timedelta(minutes=1)
        result = run(['--store', str(store.path),
                      'restore',
                      '{:%Y-%m-%d %H:%M:%S}'.format(when),
                      str(test_file),
                      '--to', str(target_file)])
        assert test_file.read_text() == 'bar'
        assert target_file.read_text() == 'foo'

    def test_existing_file_without_force(self, store, temp_dir):
        '''
        ``restore`` a file to an existing path without force.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        store.put(test_file)
        when = datetime.datetime.now() + datetime.timedelta(minutes=1)
        assert_failure(['--store', str(store.path),
                        'restore',
                        '{:%Y-%m-%d %H:%M:%S}'.format(when),
                        str(test_file)],
                       'already exists')

