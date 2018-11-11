#!/usr/bin/env python3

import logging
from pathlib import Path

import click
import watchdog.observers

from .import EventHandler, FileQueue, __version__ as coba_version
from .store import Store


@click.group()
def coba():
    log = logging.getLogger('coba')
    formatter = logging.Formatter('%(created)f [%(levelname)s] %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)


@coba.command()
@click.argument('directory')
def watch(directory):
    directory = Path(directory)
    queue = FileQueue()
    handler = EventHandler(queue)

    base = Path(__file__).resolve().parent.parent
    with Store(base / 'test-store') as store:
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


coba()

