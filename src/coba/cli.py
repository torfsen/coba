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
Command-line interface.
"""

import datetime
import functools
import logging
import os.path
import sys
import traceback

import click

from . import Coba
from .stores import local_storage_driver


log = logging.getLogger(__name__)
# Make sure no default warning is displayed if there's an error before
# logging is fully initialized.
log.addHandler(logging.NullHandler())


class _MaxLevelFilter(logging.Filter):
    """
    Logging filter that discards messages with too high a level.
    """
    def __init__(self, level):
        """
        Constructor.

        ``level`` is the maximum level (exclusive).
        """
        self.level = level

    def filter(self, record):
        return record.levelno < self.level


def _handle_errors(f):
    """
    Decorator that logs exceptions to STDERR and exits.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            log.debug(traceback.format_exc())
            sys.exit('Error: %s' % e)
    return wrapper


def _init_logging(level):
    """
    Initialize logging.

    Logging is initialized so that warnings and errors are printed
    to STDERR, anything else is printed to STDOUT.

    Any message whose level is less than ``level`` is suppressed.
    """
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(_MaxLevelFilter(logging.WARNING))
    log.addHandler(stdout_handler)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    log.addHandler(stderr_handler)
    log.setLevel(level)


def _format_revision(rev):
    return '%s %s' % (datetime.datetime.fromtimestamp(rev.timestamp),
                      rev.hashsum)


# Log levels for --verbosity option
_VERBOSITY_LOG_LEVELS = [logging.WARNING, logging.INFO, logging.DEBUG]


@click.group()
@click.pass_context
@click.option('-v', '--verbose', count=True, help='Increase verbosity of ' +
              'the output. This can be specified twice for even more output.')
@_handle_errors
def main(ctx, verbose):
    """
    Coba is a continuous backup system.

    Whenever you change a file that you have told Coba to watch, Coba
    will store a snapshot of the file's content which can be restored
    later on. For this to work, Coba's backup daemon must be running in
    the background. To start the daemon, use the `start` command:

        coba start

    The daemon can be stopped again using the `stop` command:

        coba stop

    To see which revisions Coba has stored for a given file, use the
    `revs` command:

        coba revs /path/to/the/file

    To restore a file to a certain revision, use the `restore` command:

        coba restore --hash REVISION_HASH /path/to/the/file

    Most commands print little or no output by default. You can use the
    `-v` option to show more information:

        coba -v status

    For more information on any command, use the `--help` option:

        coba restore --help
    """
    level = _VERBOSITY_LOG_LEVELS[min(verbose, len(_VERBOSITY_LOG_LEVELS) - 1)]
    _init_logging(level)
    ctx.obj = Coba()


def _command(f):
    return main.command()(click.pass_context(_handle_errors(f)))


@_command
def start(ctx):
    """
    Start the backup daemon.

    This starts Coba's backup daemon in a separate background process.
    The daemon will perform its duties until it is told to shut down
    via the `stop` command.
    """
    ctx.obj.start()


@_command
def stop(ctx):
    """
    Stop the backup daemon.

    This signals the backup daemon to stop. Because the daemon will
    complete its on-going backup activities before shutting down it
    may still be alive for a moment after the `stop` command has been
    issued. However, no new backup activities are scheduled once the
    daemon receives the stop signal.

    In case a bug prevents the daemon from stopping after the `stop`
    command has been issued you can use the `kill` command to forcibly
    kill the daemon's process.
    """
    ctx.obj.stop()


@_command
def status(ctx):
    """
    Check whether the backup daemon is running.

    The return code is 0 if the daemon is running and greater than zero
    if not.
    """
    if ctx.obj.is_running():
        print "The backup daemon is running."
        log.info('Daemon PID is %d.' % ctx.obj.get_pid())
    else:
        print "The backup daemon is not running."
        sys.exit(1)


@_command
def kill(ctx):
    """
    Kill the backup daemon.

    This forcibly kills the backup daemon's process without giving it a
    chance for a clean shutdown. Therefore, the `kill` command should
    only be used as a last resort: the standard way of stopping the
    daemon is via the `stop` command.
    """
    ctx.obj.kill()


@_command
@click.argument('PATH', type=click.Path())
@click.option('--hash', help='Revision hash')
def revs(ctx, path, hash):
    """
    List a file's revisions.

    Use the `--hash` option to only display revisions whose hash starts
    with a given value.
    """
    f = ctx.obj.file(path)
    revs = f.filter_revisions(hash=hash, unique=False)
    if revs:
        for rev in reversed(revs):
            print _format_revision(rev)
    else:
        log.info('No revisions for "%s".' % f.path)


@_command
@click.argument('PATH', type=click.Path())
@click.argument('TARGET', type=click.Path(), required=False)
@click.option('--hash', required=True, help='Revision hash')
def restore(ctx, path, target, hash):
    """
    Restore a file to a previous revision.

    The file PATH is restored to the revision specified via `--hash`.
    If TARGET is not given, the file is restored at its original
    location. If TARGET is given it can be either a filename (in which
    case the file is restored at that location) or a directory (in which
    case the file is restored in that directory using its original
    basename).

    The revision hash given using `--hash` can be partial (i.e. only a
    part of the full hash, starting from its first character) but must
    unambiguously identify a single revision. More precisely, it must
    identify a single full revision hash (which may be shared by
    multiple revisions containing the same content).

    Use the `revs` command to list available revisions for a file.
    """
    f = ctx.obj.file(path)
    revs = f.filter_revisions(hash=hash, unique=True)
    if not revs:
        raise ValueError('No revision for "%s" fits hash "%s".' % (f.path,
                         hash))
    if len(revs) > 1:
        log.info('Revisions for "%s" fitting "%s":\n    ' % (f.path, hash) +
                 '\n    '.join(_format_revision(r) for r in revs))
        raise ValueError('Hash "%s" for "%s" is ambiguous.' % (hash, f.path))
    target = revs[0].restore(target)
    if target == f.path:
        log.info('Restored content of "%s" from revision "%s".' % (f.path,
                 revs[0].hashsum ))
    else:
        log.info('Restored content of "%s" from revision "%s" to "%s".' % (
                 f.path, revs[0].hashsum, target))

