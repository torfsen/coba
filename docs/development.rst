Development
###########

Source Code
===========
The source code for Coba can be found `on GitHub
<https://github.com/torfuspolymorphus/coba>`_.


Tests
=====
Use the ``runtests.py`` script to execute the tests. Please make sure to
`create an issue <https://github.com/torfuspolymorphus/coba/issues>`_ if
any of the tests fail.


Test User and Group
-------------------
Some of the tests check if file meta-data is backed up and restored correctly.
These tests require two separate user accounts called ``coba_test_a`` and
``coba_test_b``, as well as two groups of the same names.

The ``create_test_users.sh`` script creates the users and groups. The users
are created without a home directory and cannot login. The
``remove_test_users.sh`` script removes the users and groups.

Since non-privileged users cannot change file ownership the tests that need to
modify file owners need to be run using ``sudo``. Tests which require these
privileges are collected in ``test/test_sudo.py``, so you can run them
selectively::

    sudo ./runtests.py test/test_sudo.py

.. note::
    If the test users or groups don't exist or if the tests are run without
    root privileges then the file ownership tests are automatically skipped.


API Reference
=============

.. toctree::

    coba
    coba_cli
    coba_compat
    coba_config
    coba_crypto
    coba_storage
    coba_utils
    coba_warnings
    coba_watch

