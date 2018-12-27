#!/usr/bin/env python3

import datetime
import os
from pathlib import Path
import time

from coba.utils import (local_to_utc, make_path_absolute, parse_datetime,
                        utc_to_local)

from .conftest import timezone, working_dir


def test_utc_to_local_and_local_to_utc():
    utc = datetime.datetime.strptime('2018-01-04 12:00', '%Y-%m-%d %H:%M')
    for tz, local in [
        ('America/Belize', '2018-01-04 6:00'),
        ('Australia/Sydney', '2018-01-04 23:00'),
        ('Europe/Berlin', '2018-01-04 13:00'),
    ]:
        local = datetime.datetime.strptime(local, '%Y-%m-%d %H:%M')
        with timezone(tz):
            assert utc_to_local(utc).replace(tzinfo=None) == local
            assert local_to_utc(local).replace(tzinfo=None) == utc


class TestMakePathAbsolute:
    def test_absolute_path(self):
        '''
        Make an absolute path absolute.
        '''
        path = Path('/foo/bar/baz')
        assert make_path_absolute(path) == path

    def test_relative_path(self, temp_dir):
        '''
        Make a relative path absolute.
        '''
        with working_dir(temp_dir):
            assert make_path_absolute('foo') == temp_dir / 'foo'

    def test_normalize_path(self):
        '''
        Normalization of ``..`` and ``.``.
        '''
        assert make_path_absolute('/a/../b/./d/e/.././../f') == Path('/b/f')

    def test_path_with_links(self, temp_dir):
        '''
        Make a path with links absolute.
        '''
        (temp_dir / 'a' / 'b' / 'c').mkdir(parents=True)
        os.symlink('a/b', str(temp_dir / 'x'))
        (temp_dir / 'a/b/c/d').touch()
        os.symlink('d', str(temp_dir / 'a/b/c/y'))
        with working_dir(temp_dir):
            assert make_path_absolute('x/c/y') == temp_dir / 'x/c/y'


class TestParseDatetime:
    def test_parse_datetime_valid(self):
        '''
        Parse valid datetimes.
        '''
        now = datetime.datetime.now()
        for s, dt in [
            ('2018-01-03 12:54:03', datetime.datetime(2018, 1, 3, 12, 54, 3)),
            ('2018-01-03 12:54', datetime.datetime(2018, 1, 3, 12, 54, 59)),
            ('2018-01-03', datetime.datetime(2018, 1, 3, 23, 59, 59)),
            ('12:54:03', datetime.datetime(now.year, now.month, now.day, 12, 54, 3)),
            ('12:54',  datetime.datetime(now.year, now.month, now.day, 12, 54, 59)),
        ]:
            assert parse_datetime(s) == dt
