#!/usr/bin/env python

"""
Configuration management.
"""

import codecs
import errno
import json
import os.path


class Configuration(object):
    """
    Coba configuration.

    :watched_dirs:
        A list of directories to be watched. Files within these
        directories or their subdirectories are backed up after they
        have been modified. The directories should be disjoint, i.e.
        no directory in the list should be contained in another
        directory in the list.

    :storage_dir:
       Directory where the backed up data is stored. This directory is
       created if it does not exist.

    :idle_wait_time:
       Time (in seconds) that a file has to be idle after a
       modification before it is backed up. This is a feature to avoid
       backing up files during ongoing modifications.

    :pid_dir:
        Directory where the PID lock file of the service process is
        stored.

    :log_level:
        Verbosity of the log output. The higher this value is, the less
        verbose the log output will be. A value of 10 shows debugging
        output, 20 shows general information, 30 shows warnings, and 40
        shows only errors.
    """

    def __init__(self, **kwargs):
        home = os.path.expanduser('~')
        self.watched_dirs = [home]
        self.storage_dir = os.path.join(home, '.coba', 'storage')
        self.idle_wait_time = 5
        self.pid_dir = '/tmp'
        self.log_level = 1
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

