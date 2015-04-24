#!/usr/bin/env python

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

from . import Coba, local_storage_driver


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


# Log levels for --verbosity option
_VERBOSITY_LOG_LEVELS = [logging.WARNING, logging.INFO, logging.DEBUG]


@click.group()
@click.pass_context
@click.option('-v', '--verbose', count=True)
@_handle_errors
def main(ctx, verbose):
    """
    Coba is a continuous backup system.
    """
    level = _VERBOSITY_LOG_LEVELS[min(verbose, len(_VERBOSITY_LOG_LEVELS) - 1)]
    _init_logging(level)
    storage_dir = os.path.expanduser('~/.coba/storage')
    driver = local_storage_driver(storage_dir)
    ctx.obj = Coba(driver, watched_dirs=['.'])


def _command(f):
    return main.command()(click.pass_context(_handle_errors(f)))


@_command
def start(ctx):
    """
    Start the backup daemon.
    """
    ctx.obj.start()


@_command
def stop(ctx):
    """
    Stop the backup daemon.
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
    """
    ctx.obj.kill()


@_command
@click.argument('PATH', type=click.Path())
def info(ctx, path):
    """
    Print information about a file.
    """
    f = ctx.obj.file(path)
    revs = f.get_revisions()
    if revs:
        print '%d revision(s) for "%s":\n' % (len(revs), f.path)
        for rev in reversed(revs):
             print datetime.datetime.fromtimestamp(rev.timestamp), rev.hashsum
    else:
        print 'No revisions for "%s".' % f.path


@_command
@click.argument('PATH', type=click.Path())
@click.argument('TARGET', type=click.Path(), required=False)
@click.option('--hash', required=True)
def restore(ctx, path, target, hash):
    """
    Restore a file to a previous revision.
    """
    f = ctx.obj.file(path)
    if target is None:
        target = path
    if os.path.isdir(target):
        target = os.path.join(target, f.path.name)
    candidates = []
    revs = f.get_revisions()
    if not revs:
        raise ValueError('No revisions for "%s".' % f.path)
    for rev in f.get_revisions():
        if rev.hashsum.startswith(hash):
            candidates.append(rev)
    if not candidates:
        raise ValueError('No revision for "%s" fits hash "%s".' % (f.path,
                         hash))
    if len(candidates) > 1:
        raise ValueError('Hash "%s" for "%s" is ambiguous.' % (hash, f.path))
    rev = candidates[0]
    log.info('Restoring content of "%s" from revision "%s" to "%s".' % (f.path,
             rev.hashsum, target))
    rev.restore(target)

