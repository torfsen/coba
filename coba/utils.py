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
import os.path
from pathlib import Path
import re

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


def local_to_utc(dt):
    '''
    Convert a datetime object from the local timezone to UTC.
    '''
    return dt.replace(tzinfo=tz.tzlocal()).astimezone(tz.tzutc())


def parse_datetime(s):
    '''
    Parse a string into a ``datetime.datetime``.

    Supports multiple formats. If no date is given then the current date
    is used. If no time is given then the end of the day is used. If a
    time without seconds is given then the seconds are set to 59.

    If no date/time can be parsed from the string then a ``ValueError``
    is raised.
    '''
    s = re.sub(r'\s+', ' ', s.strip())
    for format in [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%H:%M:%S',
        '%H:%M',
    ]:
        try:
            dt = datetime.datetime.strptime(s, format)
        except ValueError:
            continue
        if not '%Y' in format:
            # Date not specified
            now = datetime.datetime.now()
            dt = dt.replace(year=now.year, month=now.month, day=now.day)
        if not '%H' in format:
            # Time not specified
            dt = dt.replace(hour=23, minute=59, second=59)
        elif not '%S' in format:
            # Seconds not specified
            dt = dt.replace(second=59)
        return dt
    raise ValueError('Unknown date/time format "{}"'.format(s))

