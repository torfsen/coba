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
Tests for ``coba.crypto``.
"""

import contextlib
import functools
import io
import os.path
import sys

from nose.tools import eq_ as eq, ok_ as ok, raises
from nose.plugins.skip import SkipTest

import coba.crypto


GOT_GPGME = not coba.crypto._GPGME_ERROR

def needs_gpgme(f):
    """
    Decorator to skip tests that require PyGPGME if it isn't available.
    """
    if GOT_GPGME:
        return f

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        raise SkipTest('PyGPGME is not available.')
    return wrapper


def without_gpgme(f):
    """
    Decorator that fakes a missing PyGPGME.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        e = coba.crypto._GPGME_ERROR
        coba.crypto._GPGME_ERROR = ImportError()
        try:
            return f(*args, **kwargs)
        finally:
            coba.crypto._GPGME_ERROR = e
    return wrapper


#
# Tests for ``CryptoProvider``
#

GPG_KEY_DIR = os.path.join(os.path.dirname(__file__), 'keys')

def with_provider(recipient=None):
    def decorator(f):
        @functools.wraps(f)
        def wrapper():
            return f(coba.crypto.CryptoProvider(recipient, GPG_KEY_DIR))
        return wrapper
    return decorator


@with_provider('407F190A7FE723F4A07AB27ED4214304ACA95E87')
@needs_gpgme
def test_key_lookup_fingerprint(p):
    """
    Test recipient key lookup via fingerprint.
    """
    pass


@with_provider('test@coba')
@needs_gpgme
def test_key_lookup_email(p):
    """
    Test recipient key lookup via e-mail.
    """
    pass


@raises(coba.crypto.CryptoError)
@with_provider('no such key')
@needs_gpgme
def test_key_lookup_invalid(p):
    """
    Test recipient key lookup with invalid data.
    """
    pass


@raises(coba.crypto.CryptoError)
@with_provider('test2@coba')
@needs_gpgme
def test_key_lookup_ambiguous(p):
    """
    Test recipient key lookup with ambiguous data.
    """
    pass


@with_provider('test@coba')
@needs_gpgme
def test_encryption_decryption(p):
    """
    Test encryption and decryption.
    """
    data = b'foobar'
    encrypted_buffer = io.BytesIO()
    p.encrypt(io.BytesIO(data), encrypted_buffer)
    ok(data != encrypted_buffer.getvalue())
    encrypted_buffer.seek(0)
    decrypted_buffer = io.BytesIO()
    p.decrypt(encrypted_buffer, decrypted_buffer)
    eq(decrypted_buffer.getvalue(), data)


@raises(coba.crypto.CryptoError)
@with_provider()
@needs_gpgme
def test_encryption_without_recipient(p):
    """
    Test encryption without a recipient.
    """
    p.encrypt(None, None)


@raises(coba.crypto.CryptoGPGMEError)
@with_provider('test@coba')
@needs_gpgme
def test_encryption_gpgme_error(p):
    """
    Test exception wrapping during encryption.
    """
    p.encrypt(None, None)


@raises(coba.crypto.CryptoGPGMEError)
@with_provider('test@coba')
@needs_gpgme
def test_decryption_gpgme_error(p):
    """
    Test exception wrapping during decryption.
    """
    p.decrypt(None, None)


@raises(coba.crypto.CryptoUnavailableError)
@with_provider('test@coba')
@without_gpgme
def test_encryption_no_gpgme(p):
    """
    Test encryption without PyGPGME.
    """
    p.encrypt(None, None)


@raises(coba.crypto.CryptoUnavailableError)
@with_provider('test@coba')
@without_gpgme
def test_decryption_no_gpgme(p):
    """
    Test decryption without PyGPGME.
    """
    p.decrypt(None, None)


def test_is_encrypted():
    """
    Test recognition of OpenPGP packet data.
    """
    for case in (0xc1, 0x84, 0x85, 0x86, 0x87):
        ok(coba.crypto.is_encrypted(chr(case)))
        buf = io.BytesIO(chr(case))
        ok(coba.crypto.is_encrypted(buf))
        eq(buf.tell(), 0)
    for case in ['', 'foo']:
        ok(not coba.crypto.is_encrypted(case))
        buf = io.BytesIO(case)
        ok(not coba.crypto.is_encrypted(buf))
        eq(buf.tell(), 0)

