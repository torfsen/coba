#!/usr/bin/env python3

from pathlib import Path

import watchdog
import watchdog.events
import watchdog.observers


# Internally, ``Path`` instances are used for all file and directory paths. Raw
# paths obtained from outside are converted at the point they are obtained at.
# When external functions expect raw paths then ``Path`` instances are converted
# at the last possible moment.


class EventHandler(watchdog.events.FileSystemEventHandler):
    '''
    Event handler for file system events.
    '''
    # We do not care about deletion events, since we do not store deletions. If
    # a file is removed between being scheduled for backup and the backup
    # itself then this is handled in the backup code.

    def dispatch(self, event):
        if event.is_directory:
            return  # Ignore directory events
        super().dispatch(event)

    # In our tests, a newly created file always gets two events: first a
    # creation event, then a modification event (even if the file is empty).
    # Hence we ignore creation events.

    def on_modified(self, event):
        self._register(Path(event.src_path))

    def _register(self, path):
        print(path)

    def on_moved(self, event):
        # Watchdog only generates move events for moves within the same
        # watch. In that case, it generates no separate creation or
        # modification events for the destinations.
        self._register(Path(event.dest_path))


if __name__ == '__main__':
    import time

    HERE = Path(__file__).resolve().parent
    SANDBOX = HERE / 'sandbox'

    observer = watchdog.observers.Observer()
    observer.schedule(EventHandler(), str(SANDBOX), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Exiting.')


