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
Cryptography functionality.

This module depends on the PyGPGME_ module. Even without it you can
import this module and instantiate its classes, but trying to perform
any crypto operations will raise :py:class:`CryptoUnavailableError`.

.. _PyGPGME: https://pypi.python.org/pypi/pygpgme
"""

import functools
import os

try:
    import gpgme
    _GPGME_ERROR = None
except ImportError as e:
    _GPGME_ERROR = e


__all__ = [
    'CryptoError',
    'CryptoGPGMEError',
    'CryptoProvider',
    'CryptoUnavailableError',
    'is_encrypted',
]


class CryptoError(Exception):
    """
    General crypto error.
    """
    pass


class CryptoUnavailableError(CryptoError):
    """
    Raised if cryptographic operations are not available.

    If you receive this error then make sure that the PyGPGME_ module is
    installed.

    .. _PyGPGME: https://pypi.python.org/pypi/pygpgme
    """
    pass


class CryptoGPGMEError(CryptoError):
    """
    Raised if GPGME reports an error.

    .. py:attr:: cause

        An instance of :py:class:`gpgme.GpgmeError` with the original
        error.
    """
    def __init__(self, cause):
        """
        Constructor.

        ``cause`` is an instance of :py:class:`gpgme.GpgmeError`.
        """
        super(CryptoGPGMEError, self).__init__(cause.message)
        self.cause = cause


def _needs_crypto(f):
    """
    Decorator that raises an exception if crypto isn't available.
    """
    # We could make this check once on import time, but doing it
    # on runtime increases testability.
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if _GPGME_ERROR:
            raise CryptoUnavailableError('Crypto operations are not ' +
                                         'available: %s', _GPGME_ERROR)
        return f(*args, **kwargs)
    return wrapper


@_needs_crypto
def _get_key(ctx, s):
    """
    Find GPG key by fingerprint or other information.

    ``ctx`` is a :py:class:`gpgme.Context` and ``s`` is a string that
    describes the desired key.

    Raises a :py:class:`CryptoError` if the key could not be found
    or if the information doesn't uniquely identify a single key.
    """
    try:
        return ctx.get_key(s)
    except gpgme.GpgmeError:
        pass
    keys = list(ctx.keylist(s))
    if not keys:
        raise CryptoError('No GPG keys match "%s".' % s)
    if len(keys) > 1:
        raise CryptoError('GPG key information "%s" is ambiguous.' % s)
    return keys[0]


class CryptoProvider(object):
    """
    High-level crypto interface for encryption and decryption.
    """
    def __init__(self, recipient=None, key_dir=None):
        """
        Constructor.

        ``recipient`` is a string identifying the recipient's GPG key.
        This can either be a key fingerprint or any part of the key's
        user information that identifies the key uniquely within the
        key ring.

        ``key_dir`` is the directory containing the keys, if it is not
        specified then GPG's default will be used.
        """
        if not _GPGME_ERROR:
            self._ctx = gpgme.Context()
            self._ctx.set_engine_info(gpgme.PROTOCOL_OpenPGP, None, key_dir)
            if recipient:
                self._recipient = _get_key(self._ctx, recipient)
            else:
                self._recipient = None

    @property
    def recipient(self):
        """
        The recipient's key.

        This is either ``None`` or a :py:class:`gpgme.Key` instance with
        the GPG key of the recipient passed to
        :py:meth:`CryptoProvider.__init__`.
        """
        return self._recipient

    @_needs_crypto
    def encrypt(self, plaintext, ciphertext):
        """
        Encrypt a byte stream.

        Encrypts the byte stream in the open file-like object
        ``plaintext`` and stores the encrypted byte stream in the open
        file-like object ``ciphertext``. The encryption uses the public
        key of the recipient passed to
        :py:meth:`CryptoProvider.__init__`.
        """
        if not self._recipient:
            raise CryptoError('Cannot encrypt if no recipient is set.')
        try:
            self._ctx.encrypt([self._recipient], 0, plaintext, ciphertext)
        except gpgme.GpgmeError as e:
            raise CryptoGPGMEError(e)

    @_needs_crypto
    def decrypt(self, ciphertext, plaintext):
        """
        Decrypts a byte stream.

        Decrypts the byte stream in the open file-like object
        ``ciphertext`` and stores the decrypted byte stream in the open
        file-like object ``plaintext``.
        """
        try:
            self._ctx.decrypt(ciphertext, plaintext)
        except gpgme.GpgmeError as e:
            raise CryptoGPGMEError(e)


def is_encrypted(x):
    """
    Check if a string or file has been encrypted using GPG.

    ``x`` is either a string or an open file-like object. It is checked
    whether ``x`` contains GPG-encrypted data.

    The actual check is only a very simple heuristic: The first byte of
    ``x`` is checked to contain a valid OpenPGP packet header for a
    public-key encrypted session key packet. This means that this
    function is prone to false positives.

    If ``x`` is a file-like object then its file pointer is reset to its
    original location after the check.

    See RFC 4480 for details on the OpenPGP packet format.
    """
    if not x:
        return False
    try:
        # Assume string
        c = x[0]
    except TypeError:
        # Assume file
        c = x.read(1)
        if not c:
            # EOF
            return False
        x.seek(-1, os.SEEK_CUR)
    b = ord(c)
    if not b & 0x80:  # Bit 7
        return False
    if b & 0x40:  # Bit 6
        # New packet format
        tag = b & 0x3f  # Bits 5-0
    else:
        # Old packet format
        tag = (b & 0x3c) >> 2  # Bits 5-2
    return tag == 1  # Public-Key Encrypted Session Key Packet

