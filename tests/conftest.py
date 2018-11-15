#!/usr/bin/env python3

import contextlib
import os
from pathlib import Path
import tempfile

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

