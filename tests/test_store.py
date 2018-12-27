#!/usr/bin/env python3

import datetime
from pathlib import Path
import time
from unittest import mock

import pytest
from sealedmock import seal

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
        other_file = temp_dir / 'other.txt'
        other_file.touch()
        store_path = temp_dir / 'store'
        with Store(store_path) as store:
            store.put(other_file)
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
        other_file = temp_dir / 'other.txt'
        other_file.touch()
        with Store(store_path) as store:
            store.put(other_file)
            version = store.put(temp_dir / test_filename)
            with working_dir(temp_dir):
                assert list(store.get_versions(Path(test_filename))) == [version]

    def test_get_version_at(self, temp_dir, store):
        '''
        Test ``Store.get_version_at``.
        '''
        other_file = temp_dir / 'other.txt'
        other_file.touch()
        store.put(other_file)
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        version1 = store.put(test_file)
        time.sleep(1.1)
        test_file.write_text('bar')
        version2 = store.put(test_file)
        at1 = version1.stored_at - datetime.timedelta(minutes=1)
        at2 = version1.stored_at + (version2.stored_at - version1.stored_at) / 2
        at3 = version2.stored_at + datetime.timedelta(minutes=1)
        assert store.get_version_at(test_file, at1) is None
        assert store.get_version_at(test_file, at2) == version1
        assert store.get_version_at(test_file, at3) == version2


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

    def test_restore_default_arguments_existing_file(self, store, temp_dir):
        '''
        Default arguments of ``restore`` with an existing file.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        version = store.put(test_file)
        with pytest.raises(FileExistsError):
            version.restore()

    def test_restore_default_arguments_non_existing_file(self, store, temp_dir):
        '''
        Default arguments of ``restore`` with an non-existing file.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        version = store.put(test_file)
        test_file.unlink()
        result = version.restore()
        assert result == test_file
        assert test_file.read_text() == 'foo'

    def test_restore_relative_path(self, store, temp_dir):
        '''
        Passing a relative path to ``restore``.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        version = store.put(test_file)
        with working_dir(temp_dir):
            result = version.restore('x')
        assert result == temp_dir / 'x'
        assert result.read_text() == 'foo'

    def test_restore_unknown_hash(self, store):
        '''
        Passing a version with unknown hash to ``restore``.
        '''
        _version = mock.Mock()
        _version.hash = 'does-not-exist'
        _version.path = Path('/foo/bar')
        with pytest.raises(ValueError):
            Version(_version, store).restore()

    def test_restore_existing_file_force_false(self, store, temp_dir):
        '''
        Restore a version at an existing file without force.
        '''
        _version = mock.Mock()
        _version.path = temp_dir / 'test.txt'
        _version.path.touch()
        with pytest.raises(FileExistsError):
            Version(_version, store).restore()

    def test_restore_existing_file_force_true(self, store, temp_dir):
        '''
        Restore a version at an existing file with force.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        version = store.put(test_file)
        test_file.write_text('bar')
        version.restore(force=True)
        assert test_file.read_text() == 'foo'

    def test_restore_existing_directory(self, store, temp_dir):
        '''
        Restore a version at an existing directory.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        version = store.put(test_file)
        sub_dir = temp_dir / 'subdir'
        sub_dir.mkdir()
        result = version.restore(sub_dir)
        target_path = sub_dir / 'test.txt'
        assert result == target_path
        assert target_path.read_text() == 'foo'

    def test_restore_existing_file_in_existing_directory_force_false(self,
                                                                     store,
                                                                     temp_dir):
        '''
        Restore a version at an existing file in an existing directory
        without force.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        version = store.put(test_file)
        sub_dir = temp_dir / 'subdir'
        sub_dir.mkdir()
        target_path = sub_dir / 'test.txt'
        target_path.touch()
        with pytest.raises(FileExistsError):
            version.restore(sub_dir)

    def test_restore_existing_file_in_existing_directory_force_true(self,
                                                                    store,
                                                                    temp_dir):
        '''
        Restore a version at an existing file in an existing directory
        with force.
        '''
        test_file = temp_dir / 'test.txt'
        test_file.write_text('foo')
        version = store.put(test_file)
        sub_dir = temp_dir / 'subdir'
        sub_dir.mkdir()
        target_path = sub_dir / 'test.txt'
        target_path.write_text('bar')
        result = version.restore(sub_dir, force=True)
        assert result == target_path
        assert target_path.read_text() == 'foo'

