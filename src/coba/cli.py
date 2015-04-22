#!/usr/bin/env python

"""
Command-line interface.
"""

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


@main.command()
@click.pass_context
@_handle_errors
def start(ctx):
    """
    Start the backup daemon.
    """
    ctx.obj.start()


@main.command()
@click.pass_context
@_handle_errors
def stop(ctx):
    """
    Stop the backup daemon.
    """
    ctx.obj.stop()


@main.command()
@click.pass_context
@_handle_errors
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


@main.command()
@click.pass_context
@_handle_errors
def kill(ctx):
    """
    Kill the backup daemon.
    """
    ctx.obj.kill()

