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
Configuration management.
"""

import codecs
import errno
import json
import os.path

import pathlib

from .utils import is_in_dir, match_path


class Configuration(object):
    """
    Coba configuration.

    :idle_wait_time:
       Time (in seconds) that a file has to be idle after a
       modification before it is backed up. This is a feature to avoid
       backing up files during ongoing modifications.

    :ignored:
        Files that should be ignored. This is a list of patterns, a file
        that matches at least one of these patterns is ignored by Coba.
        The syntax for the patterns is that of Python's ``fnmatch``
        module. Matching is done case-sensitively.

    :log_level:
        Verbosity of the log output. The higher this value is, the less
        verbose the log output will be. A value of 10 shows debugging
        output, 20 shows general information, 30 shows warnings, and 40
        shows only errors. This only controls the output of the backup
        daemon to syslog. The verbosity of the ``coba`` command line
        utility can be controlled via its ``-v`` argument.

    :pid_dir:
        Directory where the PID lock file of the service process is
        stored.

    :storage_dir:
       Directory where the backed up data is stored. This directory is
       created if it does not exist.

    :watched_dirs:
        A list of directories to be watched. Files within these
        directories or their subdirectories are backed up after they
        have been modified. The directories should be disjoint, i.e.
        no directory in the list should be contained in another
        directory in the list.
    """

    def __init__(self, **kwargs):
        home = os.path.expanduser('~')
        self.idle_wait_time = 5
        self.ignored = ['**/.*']
        self.log_level = 1
        self.pid_dir = '/tmp'
        self.storage_dir = os.path.join(home, '.coba', 'storage')
        self.watched_dirs = [home]
        for key, value in kwargs.iteritems():
            if (not key.startswith('_')) and hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(key)

    @staticmethod
    def default_location():
        return os.path.join(os.path.expanduser('~'), '.coba', 'config')

    @classmethod
    def load(cls, path=None):
        """
        Load configuration from file.

        If ``path`` is not given the default location is used. If it
        doesn't exist then the default configuration is returned.
        """
        if not path:
            path = cls.default_location()
            try:
                with open(path) as f:
                    data = json.load(f)
            except IOError as e:
                if e.errno == errno.ENOENT:
                    return cls()
                raise
        else:
            with codecs.open(path, 'r', encoding='utf8') as f:
                data = json.load(f)
        return cls(**data)

    def save(self, path=None):
        """
        Save configuration in file.

        If ``path`` is not given the default location is used.
        """
        path = path or default_location()
        attrs = {key:value for key, value in self.__dict__.iteritems() if not
                 key.startswith('_')}
        with codecs.open(path, 'w', encoding='utf8') as f:
            json.dump(attrs, f)

    def is_ignored(self, path):
        """
        Check if a file is ignored.
        """
        if is_in_dir(path, self.storage_dir):
            return True
        for pattern in self.ignored:
            if match_path(pattern, path):
                return True

