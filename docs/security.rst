Security
########

To securely store backup data in the cloud the data needs to be secured against
unauthorized access. Coba uses different approaches for securing information
in file content and filenames.

.. note::

    If you encrypt your backup data (which you should do) then take special
    care of your encryption key and its passphrase. Without the key and the
    passphrase you won't be able to restore any backups!


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

.. _GPG: https://www.gnupg.org/


Filenames
=========

Filenames may contain sensitive information, too. To protect it, filenames are
hashed using a salted PBKDF2_ hash based on 100000 rounds of SHA-1_. Each
filename uses a separate random 16 byte salt which is stored along with the
backup data. If an encryption key is specified then the salts are encrypted.

.. _PBKDF2: https://en.wikipedia.org/wiki/PBKDF2
.. _SHA-1: https://en.wikipedia.org/wiki/SHA-1


Changing the Encryption Key
===========================

Data is only encrypted during write-access. This means that any file content
backed up before an encryption key is specified is stored unencrypted even
after an encryption key is added. Similarly, if you change (or remove) the
:ref:`config_encryption_key` setting then backup data encrypted using the old
encryption key is not re-encrypted using the new key (or decrypted).

Since a file's complete meta-data is rewritten everytime a backup is made
creating backups encrypts the meta-data using the current key.

Salts are stored in a more complex fashion and it is currently non-trivial to
figure out which salt is encrypted using which key if the key has changed.

.. note::

    Ideally you should configure the encryption key once before any backups are
    made and don't change it afterwards.

