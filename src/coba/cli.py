#!/usr/bin/env python

"""
Command-line interface.
"""

import datetime
import functools
import os.path
import sys

import click

from . import Coba, local_storage_driver


def _handle_errors(f):
    """
    Decorator that logs exceptions to STDERR and exits.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            sys.exit(e)
    return wrapper


@click.group()
@click.pass_context
@_handle_errors
def main(ctx):
    """
    Coba is a continuous backup system.
    """
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
    if target is None:
        target = path
    f = ctx.obj.file(path)
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
    print 'Restoring content of "%s" from revision "%s" to "%s".' % (
            f.path, rev.hashsum, target)
    rev.restore(target)

