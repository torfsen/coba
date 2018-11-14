#!/usr/bin/env python3

import contextlib
import os
from pathlib import Path
import tempfile

import pytest


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@contextlib.contextmanager
def working_dir(w):
    old_dir = os.getcwd()
    os.chdir(str(w))
    try:
        yield
    finally:
        os.chdir(old_dir)

