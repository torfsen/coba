Configuration
#############

Coba's configuration is stored in a JSON_ file at ``~/.coba/config.json``.


.. _JSON: http://www.json.org


Settings
========

.. _config_idle_wait_time:

``idle_wait_time``
------------------
Time (in seconds) that a file has to be idle after a modification before it is
backed up. This feature avoids backing up files during ongoing modifications.

**Default:** ``5``


.. _config_ignored:

``ignored``
-----------
List of patterns for filenames that should be ignored. A file whose absolute
path matches at least one of these patterns is ignored by Coba. The pattern
syntax is as follows:

* A single ``*`` matches 0 or more arbitrary characters, except ``/``. For
  example, ``a*b`` matches ``ab``, ``a1b`` and ``a12b`` but not ``a/b`` or
  ``a/1/b``.

* A ``?`` matches exactly 1 arbitrary character, except ``/``. For example,
  ``a?b`` matches ``a1b`` and ``a2b`` but not ``ab``, ``a/b`` or ``a12b``.

Double asterisks (``**``) are used for matching multiple directories:

* A trailing ``/**`` matches everything in the preceeding directory. For
  example, ``a/**`` matches ``a``, ``a/`` and ``a/b/c``.

* A leading ``**/`` matches in all directories. For example, ``**/a`` matches
  ``a``, ``/a``, ``b/a``, and ``c/b/a``.

* ``/**/`` matches one or more directories. For example, ``a/**/b`` matches
  ``a/b``, ``a/1/b``, and ``a/1/2/b`` but not ``a12b``.

Any other use of ``**`` is invalid.

Use ``\`` to escape a special character: ``\*`` matches ``*`` but not ``foo``.
To match a single ``\`` use ``\\``.


**Default:** ``["**/.*"]`` (this ignores all files and directories whose name
starts with a dot)


.. _config_log_level:

``log_level``
-------------
Verbosity of the log output. The higher this value is, the less verbose the
log output will be. A value of 10 shows debugging output, 20 shows general
information, 30 shows warnings, and 40 shows only errors.

This only controls the output of the :ref:`backup daemon <usage_daemon>` to
syslog. The verbosity of the ``coba`` command line utility can be controlled
via its ``-v`` argument.

**Default:** ``1``


.. _config_pid_dir:

``pid_dir``
-----------
Directory where the PID lock file of the :ref:`backup daemon <usage_daemon>`
is stored. This directory is created if it does not exist.

**Default:** ``~/.coba``


.. _config_storage_dir:

``storage_dir``
---------------
Directory where the backed up data is stored. This directory is created if it
does not exist.

**Default:** ``~/.coba/storage``


.. _config_watched_dirs:

``watched_dirs``
----------------
A list of directories to be watched. Files within these directories or their
subdirectories are backed up after they have been modified. The directories
must be disjoint, i.e. no directory in the list should be contained in another
directory in the list.

**Default:** ``["~"]``


Example Configuration
=====================
The following example configuration file corresponds to the default configuration.

::

    {
        "idle_wait_time": 5,
        "ignored": ["**/.*"],
        "log_level": 1,
        "pid_dir": "~/.coba",
        "storage_dir": "~/.coba/storage",
        "watched_dirs": ["~"]
    }

