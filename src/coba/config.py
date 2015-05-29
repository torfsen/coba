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
Coba's configuration management.
"""

import codecs
import errno
import json
import os.path

from .utils import expand_path, is_in_dir, match_path


class Configuration(object):
    """
    Coba configuration.

    This class encapsulates the configuration of a Coba instance. The
    following configuration settings are available as instance
    attributes:

    .. py:attribute:: idle_wait_time

        Time (in seconds) that a file has to be idle after a
        modification before it is backed up. This is a feature to avoid
        backing up files during ongoing modifications.

    .. py:attribute:: ignored

        Files that should be ignored. This is a list of patterns, a file
        that matches at least one of these patterns is ignored by Coba.
        The syntax for the patterns is that of
        :py:func:`coba.utils.match_path`.

    .. py:attribute:: log_dir

        Directory in which Coba's log files are stored. This directory
        is created if it does not exist.

    .. py:attribute:: log_level

        Verbosity of the log output. The higher this value is, the less
        verbose the log output will be. A value of 10 shows debugging
        output, 20 shows general information, 30 shows warnings, and 40
        shows only errors. This only controls the output of the backup
        daemon to syslog. The verbosity of the ``coba`` command line
        utility can be controlled via its ``-v`` argument.

    .. py:attribute:: pid_dir

        Directory where the PID lock file of the service process is
        stored.

    .. py:attribute:: storage_dir

        Directory where the backed up data is stored. This directory is
        created if it does not exist.

    .. py:attribute:: watched_dirs

        A list of directories to be watched. Files within these
        directories or their subdirectories are backed up after they
        have been modified. The directories should be disjoint, i.e.
        no directory in the list should be contained in another
        directory in the list.

    In addition, the following configuration values are automatically
    derived from the other settings and can only be read:

    .. py:attribute:: log_file

        Filename of Coba's log file. Derived from :py:attr:`log_dir`.
    """

    def __init__(self, **kwargs):
        """
        Constructor.

        Any configuration setting can be set using a keyword argument.
        """
        home = expand_path('~')
        coba_dir = os.path.join(home, '.coba')
        self.idle_wait_time = 5
        self.ignored = ['**/.*/**']
        self.log_dir = os.path.join(coba_dir, 'log')
        self.log_level = 1
        self.pid_dir = coba_dir
        self.storage_dir = os.path.join(coba_dir, 'storage')
        self.watched_dirs = [home]
        for key, value in kwargs.iteritems():
            if (not key.startswith('_')) and hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(key)

    @property
    def log_file(self):
        return os.path.join(self.log_dir, 'coba.log')

    @staticmethod
    def default_location():
        """
        Returns the default location of the Coba configuration file.
        """
        return os.path.join(expand_path('~'), '.coba', 'config.json')

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
        data['ignored'] = [expand_path(p) for p in data['ignored']]
        data['pid_dir'] = expand_path(data['pid_dir'])
        data['storage_dir'] = expand_path(data['storage_dir'])
        data['watched_dirs'] = [expand_path(p) for p in data['watched_dirs']]
        return cls(**data)

    def save(self, path=None):
        """
        Save configuration in file.

        If ``path`` is not given the default location is used.
        """
        path = path or self.default_location()
        attrs = {key: value for key, value in self.__dict__.iteritems() if not
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

