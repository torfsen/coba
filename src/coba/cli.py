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
    CLI entry point.
    """
    storage_dir = os.path.expanduser('~/.coba/storage')
    driver = local_storage_driver(storage_dir)
    ctx.obj = Coba(driver)


@main.command()
@click.pass_context
def start(ctx):
    ctx.obj.loop()

