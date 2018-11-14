#!/usr/bin/env python3

import os.path
from pathlib import Path


def make_path_absolute(p):
    '''
    Make a ``pathlib.Path`` absolute.

    Does not resolve symbolic links.
    '''
    return Path(os.path.normcase(os.path.abspath(str(p))))

