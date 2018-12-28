#!/usr/bin/env python3

# Copyright (c) 2018 Florian Brucker (mail@florianbrucker.de).
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

import datetime
import functools
import logging
from pathlib import Path
import sys

import click
import watchdog.observers

from .import EventHandler, FileQueue, __version__ as coba_version
from .store import Store
from .utils import (local_to_utc, make_path_absolute, parse_datetime,
                    utc_to_local)


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
@click.option('--store', envvar='COBA_STORE', type=click.Path(file_okay=False,
              writable=True))
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
        base = make_path_absolute(Path(__file__)).parent.parent
        store = base / 'test-store'
    ctx.obj['store'] = Store(store)


@coba.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.pass_context
@_handle_errors
def watch(ctx, directory):
    '''
    Watch a directory for changes.
    '''
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
@click.argument('path', type=click.Path(dir_okay=False))
@click.pass_context
@_handle_errors
def versions(ctx, path):
    '''
    List the versions of a file.
    '''
    path = Path(path)
    with ctx.obj['store'] as store:
        for version in store.get_versions(path):
            stored_at = utc_to_local(version.stored_at)
            click.echo('{:%Y-%m-%d %H:%M:%S}'.format(stored_at))


@coba.command()
@click.option('--force/--no-force', '-f/-F', default=False)
@click.option('--to', '-t', type=click.Path(dir_okay=False, writable=True))
@click.argument('when')
@click.argument('path', type=click.Path(dir_okay=False))
@click.pass_context
@_handle_errors
def restore(ctx, force, to, when, path):
    '''
    Restore a version of a file.
    '''
    path = make_path_absolute(path)
    at = local_to_utc(parse_datetime(when))
    with ctx.obj['store'] as store:
        version = store.get_version_at(path, at)
        if not version:
            raise ValueError('No version in store for {} at {}'.format(path, when))
        stored_at = utc_to_local(version.stored_at)
        restore_path = version.restore(target_path=to, force=force)
        if to:
            click.echo('Restored version {:%Y-%m-%d %H:%M:%S} of {} to {}'.format(
                       stored_at, path, to))
        else:
            click.echo('Restored version {:%Y-%m-%d %H:%M:%S} of {}'.format(
                       stored_at, path))

