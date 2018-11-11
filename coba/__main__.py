#!/usr/bin/env python3

import logging
from pathlib import Path

import click
from dateutil import tz
import watchdog.observers

from .import EventHandler, FileQueue, __version__ as coba_version
from .store import Store


def utc_to_local(dt):
    '''
    Convert a datetime object from UTC to the local timezone.
    '''
    return dt.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal())


@click.group()
@click.pass_context
def coba(ctx):
    ctx.ensure_object(dict)

    log = logging.getLogger('coba')
    formatter = logging.Formatter('%(created)f [%(levelname)s] %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)

    base = Path(__file__).resolve().parent.parent
    ctx.obj['store'] = Store(base / 'test-store')

@coba.command()
@click.argument('directory')
@click.pass_context
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
def show(ctx, path):
    path = Path(path)
    with ctx.obj['store'] as store:
        for version in store.get_versions(path):
            stored_at = utc_to_local(version.stored_at)
            print('{:%Y-%m-%d %H:%M:%S}'.format(stored_at))


coba()

