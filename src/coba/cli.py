#!/usr/bin/env python

"""
Command-line interface.
"""

import os.path

import click

from . import Coba, local_storage_driver


@click.group()
@click.pass_context
def main(ctx):
    """
    Coba is a continuous backup system.
    """
    storage_dir = os.path.expanduser('~/.coba/storage')
    driver = local_storage_driver(storage_dir)
    ctx.obj = Coba(driver, watched_dirs=['/tmp'])


@main.command()
@click.pass_context
def start(ctx):
    """
    Start the backup daemon.
    """
    ctx.obj.start()

@main.command()
@click.pass_context
def stop(ctx):
    """
    Stop the backup daemon.
    """
    ctx.obj.stop()

@main.command()
@click.pass_context
def kill(ctx):
    """
    Kill the backup daemon.
    """
    ctx.obj.kill()

