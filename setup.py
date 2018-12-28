#!/usr/bin/env python3

# Copyright (c) 2018 Florian Brucker (mail@florianbrucker.de).
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

from pathlib import Path
import re

from setuptools import setup, find_packages


HERE = Path(__file__).resolve().parent

# Read __version__ from __init__.py
INIT_PY = HERE / 'coba' / '__init__.py'
with INIT_PY.open(encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        m = re.match(r'''__version__\s*=\s*['"](.*)['"]''', line)
        if m:
            version = m.groups()[0]
            break
    else:
        raise RuntimeError('Could not extract version from "%s".' % INIT_PY)

# Read long description from README.rst
with (HERE / 'README.rst').open(encoding='utf-8') as f:
    long_description = f.read()

# Read dependencies from requirements.in
with (HERE / 'requirements.in').open(encoding='utf-8') as f:
    install_requires = list(f.readlines())

setup(
    name='coba',
    version=version,
    description='Continuous backups',
    long_description=long_description,
    url='https://github.com/torfsen/coba',
    author='Florian Brucker',
    author_email='mail@florianbrucker.de',
    classifiers=[
        # See https://pypi.org/classifiers/
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Archiving :: Backup',
    ],
    keywords='backup',
    packages=find_packages('coba'),
    install_requires=install_requires,
    entry_points='''
        [console_scripts]
        coba=coba.__main__:coba
    ''',
)
