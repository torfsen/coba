#!/usr/bin/env python3

import logging
from pathlib import Path

import watchdog.observers

from .import EventHandler, FileQueue
from .store import Store


log = logging.getLogger()
formatter = logging.Formatter('%(created)f [%(levelname)s] %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
log.addHandler(handler)
log.setLevel(logging.DEBUG)

BASE = Path(__file__).resolve().parent.parent
SANDBOX = BASE / 'sandbox'

store = Store(BASE / 'test-store')

observer = watchdog.observers.Observer()
queue = FileQueue()
handler = EventHandler(queue)
observer.schedule(handler, str(SANDBOX), recursive=True)
observer.start()
log.info('Watching {}'.format(SANDBOX))
try:
    for path in queue:
        store.put(path)
except KeyboardInterrupt:
    log.info('Received CTRL+C')
log.info('Stopping observer...')
observer.stop()
log.info('Waiting for observer to stop...')
observer.join()
log.info('Exiting.')
