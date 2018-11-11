#!/usr/bin/env python3

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

)
