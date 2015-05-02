Usage
#####


.. _usage_daemon:

The Coba Daemon
===============
The main work of Coba is done by its *daemon*, a program that runs in the
background and backs up files after they have been modified. When the daemon
is not running you can still :ref:`restore files <restoring_files>`, but no
:ref:`new backups <usage_backups>` are performed.

To start the daemon use the ``start`` command::

    $ coba start

.. note::
    Remember that the ``coba`` command line utility is only available if you
    :doc:`activate Coba's virtual environment <installation>`.

You can always check whether the daemon is running using the ``status``
command::

    $ coba status
    The backup daemon is running.

In case you need to stop the daemon, simply use the ``stop`` command::

    $ coba stop
    $ coba status
    The backup daemon is not running.

.. note::
    Stopping the daemon may take some time, since the daemon will complete
    all scheduled backup activities before shutting down. The ``stop`` command
    returns immediately, however. If you need to be sure that the daemon has
    completely stopped use the ``status`` command.

The daemon uses syslog_ to output messages. How you can view these depends on
your *syslog* configuration. For example, on Ubuntu the following command
displays the latest messages from the daemon::

    $ grep coba /var/log/syslog


.. _syslog: https://en.wikipedia.org/wiki/Syslog


.. _usage_backups:

How Backups are Created
=======================
Coba stores a snapshot of a file's content every time the file changes,
assuming the Coba :ref:`daemon <usage_daemon>` is running, the file is in a
:ref:`watched directory <config_watched_dirs>` and it is not :ref:`ignored
<config_ignored>`. These snapshots are called *revisions* and you can display
them using the ``revs`` command::

    $ coba revs example.txt
    2015-05-02 11:43:52.116253 53c234e5e8472...
    2015-05-02 11:42:25.354735 4355a46b19d34...

Each line of the output above shows the details of a single revision: The date
and time the revision was created and a hash_ of the file's content at that
moment.

If we now edit ``example.txt``, a new revision will be created::

    $ echo foo > example.txt
    $ coba revs example.txt
    2015-05-02 14:08:37.836287 b5bb9d8014a0f...
    2015-05-02 11:43:52.116253 53c234e5e8472...
    2015-05-02 11:42:25.354735 4355a46b19d34...

.. note::
    To increase efficiency, Coba does not backup modified files immediately
    but only after :ref:`a small delay <config_idle_wait_time>`.


.. _hash: https://en.wikipedia.org/wiki/Cryptographic_hash_function#File_or_data_identifier


.. _restoring_files:

Restoring Files
===============
Continuing our :ref:`previous example <usage_backups>`, let's assume that we
regret our last edit of ``example.txt`` and want to restore the previous
revision. This is easy using the ``restore`` command::

    $ coba -v restore --hash 53 example.txt
    Restored content of "example.txt" from revision "53c234e5e8472...".

The value of the ``--hash`` option is the hash of the revision that we want to
restore. To make your life easier you only need to specify enough characters
to uniquely identify one of the revisions.

.. note::
    The ``-v`` option tells Coba to display more information. It works with all
    Coba commands and goes before the command and its argumens.

By default, restoring a revision replaces the original file. You can also
restore it somewhere else::

    $ coba -v restore --hash 53 example.txt restored.txt
    Restored content of "example.txt" from revision "53c234e5e8472..."
    to "restored.txt".

