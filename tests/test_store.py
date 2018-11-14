#!/usr/bin/env python3

import datetime
from pathlib import Path
from unittest import mock

import pytest

from coba.store import Store, Version

from .conftest import working_dir


class TestStore:

    def test_create_store_with_relative_path(self, temp_dir):
        '''
        Create a store using a relative path.
        '''
        with working_dir(temp_dir):
            with Store(Path('store')) as store:
                store_path = temp_dir / 'store'
                assert store.path == store_path
                assert store_path.is_dir()

    def test_create_store_in_nonexisting_directory(self, temp_dir):
        '''
        Create a store in a nonexisting directory.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.touch()
        with Store(temp_dir / 'new') as store:
            version = store.put(test_file)
            versions = store.get_versions(test_file)
            assert list(versions) == [version]

    def test_create_store_in_existing_file(self, temp_dir):
        '''
        Try to create a store in an existing file.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.touch()
        with pytest.raises(FileExistsError):
            with Store(test_file) as store:
                pass

    def test_open_existing_store(self, temp_dir):
        '''
        Open an existing store.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.touch()
        store_path = temp_dir / 'store'
        with Store(store_path) as store:
            version = store.put(test_file)
        with Store(store_path) as store:
            versions = store.get_versions(test_file)
            assert list(versions) == [version]

    def test_put_existing_file(self, temp_dir):
        '''
        Put an existing file into the store.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.touch()
        store_path = temp_dir / 'store'
        with Store(store_path) as store:
            version = store.put(test_file)
            age = (datetime.datetime.utcnow() - version.stored_at).total_seconds()
            assert 0 < age < 2
            assert version.path == test_file

    def test_put_nonexisting_path(self, temp_dir):
        '''
        Put a non-existing path into the store.
        '''
        store_path = temp_dir / 'store'
        with Store(store_path) as store:
            with pytest.raises(FileNotFoundError):
                store.put(temp_dir / 'not-existing')

    def test_put_relative_path(self, temp_dir):
        '''
        Put a file into the store using a relative path.
        '''
        test_filename = 'test.txt'
        (temp_dir / test_filename).touch()
        store_path = temp_dir / 'store'
        with Store(store_path) as store:
            with working_dir(temp_dir):
                version = store.put(Path(test_filename))
            assert version.path == temp_dir / test_filename

    def test_put_directory(self, temp_dir):
        '''
        Put a directory into the store.
        '''
        subdir_path = temp_dir / 'subdir'
        subdir_path.mkdir()
        store_path = temp_dir / 'store'
        with Store(store_path) as store:
            with pytest.raises(IsADirectoryError):
                store.put(subdir_path)

    def test_get_versions(self, temp_dir):
        '''
        Get the versions of a file.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.touch()
        store_path = temp_dir / 'store'
        with Store(store_path) as store:
            versions = []
            for i in range(5):
                version = store.put(test_file)
                assert isinstance(version.path, Path)
                versions.append(version)
                assert list(store.get_versions(test_file)) == versions
                test_file.write_text(str(i))
        for i in range(4):
            assert versions[i].stored_at < versions[i + 1].stored_at

    def test_get_versions_of_relative_path(self, temp_dir):
        '''
        Get the versions of a file using a relative path.
        '''
        store_path = temp_dir / 'store'
        test_filename = 'test.txt'
        (temp_dir / test_filename).touch()
        with Store(store_path) as store:
            version = store.put(temp_dir / test_filename)
            with working_dir(temp_dir):
                assert list(store.get_versions(Path(test_filename))) == [version]


class TestVersion:
    def test_eq(self):
        '''
        Equality of versions.
        '''
        _version1 = mock.Mock()
        version1 = Version(_version1, None)
        assert version1 == version1
        assert None != version1
        assert version1 != _version1
        assert _version1 != version1
        assert version1 != _version1
        assert 1 != version1
        assert version1 != 1

        _version2 = mock.Mock()
        version2 = Version(_version2, None)
        assert version1 == version2

        _version1.x = 'hello'
        _version2.x = 'hello'
        assert version1 == version2

        _version1.y = 'foo'
        assert version1 != version2
        assert version2 != version1
        _version2.y = 'foo'
        assert version1 == version2

