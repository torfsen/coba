#!/usr/bin/env python3

import os.path
from pathlib import Path

from dateutil import tz


def make_path_absolute(p):
    '''
    Make a ``pathlib.Path`` absolute.

    Does not resolve symbolic links.
    '''
    return Path(os.path.normcase(os.path.abspath(str(p))))


def utc_to_local(dt):
    '''
    Convert a datetime object from UTC to the local timezone.
    '''
    return dt.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal())

