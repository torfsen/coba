#!/usr/bin/env python3

import functools
import logging
from pathlib import Path
import sys

import click
import watchdog.observers

from .import EventHandler, FileQueue, __version__ as coba_version
from .store import Store
from .utils import utc_to_local


__all__ = ['coba']


def _handle_errors(f):
    @functools.wraps(f)
    def wrapper(ctx, *args, **kwargs):
        try:
            return f(ctx, *args, **kwargs)
        except Exception as e:
            try:
                log = ctx.obj['log']
            except KeyError:
                # Logging hasn't been set up, yet
                sys.stderr.write('Error: {}\n'.format(e))
            else:
                log.exception(e)
            sys.exit(1)
    return wrapper


@click.group()
@click.option('--store', envvar='COBA_STORE')
@click.pass_context
@_handle_errors
def coba(ctx, store):
    ctx.ensure_object(dict)

    ctx.obj['log'] = logging.getLogger('coba')
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    ctx.obj['log'].addHandler(handler)
    ctx.obj['log'].setLevel(logging.DEBUG)

    if store:
        store = Path(store)
    else:
        base = Path(__file__).resolve().parent.parent
        store = base / 'test-store'
    ctx.obj['store'] = Store(store)


@coba.command()
@click.argument('directory')
@click.pass_context
@_handle_errors
def watch(ctx, directory):
    directory = Path(directory)
    queue = FileQueue()
    handler = EventHandler(queue)
    with ctx.obj['store'] as store:
        observer = watchdog.observers.Observer()
        observer.schedule(handler, str(directory), recursive=True)
        observer.start()
        click.echo('Watching {}'.format(directory))
        try:
            for path in queue:
                store.put(path)
        except KeyboardInterrupt:
            click.echo('Received CTRL+C')
        click.echo('Stopping observer...')
        observer.stop()
        click.echo('Waiting for observer to stop...')
        observer.join()

    click.echo('Exiting.')


@coba.command()
@click.argument('path')
@click.pass_context
@_handle_errors
def show(ctx, path):
    path = Path(path)
    with ctx.obj['store'] as store:
        for version in store.get_versions(path):
            stored_at = utc_to_local(version.stored_at)
            click.echo('{:%Y-%m-%d %H:%M:%S}'.format(stored_at))

