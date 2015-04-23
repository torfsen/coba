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
@click.argument('PATH')
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

