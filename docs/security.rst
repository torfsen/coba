Security
########

To securely store backup data in the cloud the data needs to be secured against
unauthorized access. Coba uses different approaches for securing information
in file content and filenames.


File Content and Meta-Data
==========================

To protect the content of backed up files, Coba supports encryption of both the
file content itself and the backup meta-data (e.g. when a revision was
created). Encryption is performed using GPG_ and can be enabled using the
:ref:`config_encryption_key` configuration setting.

Once an encryption key is specified, all new revisions are automatically
encrypted (provided that the PyGPGME package :ref:`has been installed
<pygpgme_installation>`). When accessing encrypted revisions you will be
prompted for the encryption key's passphrase.

.. note::

    Any file content backed up before an encryption key is specified is stored
    unencrypted even after an encryption key is added. Similarly, if you
    change (or remove) the ``encryption_key`` setting then backup data
    encrypted using the old encryption key is not re-encrypted using the new
    key (or decrypted).

    This does not apply to meta-data, which is always encrypted using the
    current encryption key.

.. note::

    If you encrypt your backup data (which you should do) then take special
    care of your encryption key and its passphrase. Without the key and the
    passphrase you won't be able to restore any backups!

.. _GPG: https://www.gnupg.org/


Filenames
=========

Filenames may contain sensitive information, too. Coba's architecture currently
does not allow the encryption of filenames. Instead, filenames are hashed using
a salted PBKDF2_ hash based on 100000 rounds of SHA-1_. The salt is stored in
plain text in along with the backup data. Note that the same salt is used for
all filenames.

.. note::

    While this scheme provides a certain security it does not protect your
    filenames from an attacker with lots of time and computing power.

.. _PBKDF2: https://en.wikipedia.org/wiki/PBKDF2
.. _SHA-1: https://en.wikipedia.org/wiki/SHA-1
