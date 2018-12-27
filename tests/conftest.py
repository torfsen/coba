#!/usr/bin/env python3

import contextlib
import os
from pathlib import Path
import tempfile
import time

import pytest

from coba.store import Store


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as d:
        with Store(Path(d)) as store:
            yield store


@contextlib.contextmanager
def working_dir(w):
    old_dir = os.getcwd()
    os.chdir(str(w))
    try:
        yield
    finally:
        os.chdir(old_dir)


@contextlib.contextmanager
def timezone(tz):
    '''
    Temporarily switch to a certain timezone.
    '''
    old_tz = os.environ.get('TZ', '')
    os.environ['TZ'] = tz
    time.tzset()
    try:
        yield
    finally:
        os.environ['TZ'] = old_tz
        time.tzset()
