#!/usr/bin/env python3

from click.testing import CliRunner

from coba.cli import coba
from coba.utils import utc_to_local

from .conftest import working_dir


def run(args, expect='success'):
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(coba, args, catch_exceptions=False)
    if expect == 'success':
        assert result.exit_code == 0
    elif expect == 'failure':
        assert result.exit_code != 0
    return result


class TestWatch:
    def test_no_argument(self):
        '''
        Run ``watch`` without specifying a directory.
        '''
        result = run(['watch'], expect='failure')
        assert 'missing argument' in result.stderr.lower()
        assert not result.stdout

    def test_nonexisting_path(self):
        '''
        Run ``watch`` on a path that doesn't exist.
        '''
        result = run(['watch', '/does/not/exist'], expect='failure')
        assert 'path is not a directory' in result.stderr.lower()

    def test_not_a_directory(self, temp_dir):
        '''
        Run ``watch`` on an existing path that is not a directory.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.touch()
        result = run(['watch', str(test_file)], expect='failure')
        assert 'path is not a directory' in result.stderr.lower()

    # TODO: Test backup operation once config options can be properly set


class TestShow:
    def test_no_argument(self):
        '''
        Run ``show`` without any arguments.
        '''
        result = run(['show'], expect='failure')
        assert 'missing argument' in result.stderr.lower()
        assert not result.stdout

    def test_no_versions(self, temp_dir):
        '''
        Run ``show`` on a file without versions.
        '''
        result = run(['--store', str(temp_dir), 'show', '/does/not/exist'])
        assert not result.stdout

    def test_one_and_multiple_versions(self, store, temp_dir):
        '''
        Run ``show`` on a file with one and multiple versions.
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
            result = run(['--store', str(store.path), 'show', str(test_file)])
            assert result.stdout == expected_output
            # Test with relative path
            with working_dir(temp_dir):
                result = run(['--store', str(store.path), 'show', 'test.txt'])
                assert result.stdout == expected_output

