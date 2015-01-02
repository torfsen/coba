#!/usr/bin/env python

"""
The coba background service.
"""

import logging
import logging.handlers
import os
import time

import daemon
import lockfile

_NAME = 'coba-daemon'
_PID_FILE_PATH = '/home/torf/tmp/%s.pid' % _NAME

logger = logging.getLogger(_NAME)
_handler = logging.handlers.SysLogHandler(address='/dev/log')
_format = '%(name)s: <%(levelname)s> %(message)s'
_handler.setFormatter(logging.Formatter(_format))
logger.addHandler(_handler)
logger.setLevel(logging.DEBUG)


# Taken from python-daemon
def detach_process():
    # To detach from our process group we need to call ``setsid``. We
    # can only do that if we aren't a process group leader. Therefore
    # we fork once, which makes sure that the new child process is not
    # a process group leader.
    pid = os.fork()
    if pid > 0:
        # Parent process
        return pid
    os.setsid()
    # We now fork a second time and let the second's fork parent exit.
    # This makes the second fork's child process an orphan. Orphans are
    # cleaned up by the init process, so we won't end up with a zombie.
    # In addition, the second fork's child is no longer a session
    # leader and can therefore never acquire a controlling terminal.
    pid = os.fork()
    if pid > 0:
        logger.info("Second fork's parent here, I'm exiting.")
        os._exit(os.EX_OK)
    return 0


class Daemon(object):

    def __init__(self):
        self._pid_file = lockfile.FileLock(_PID_FILE_PATH)
        self._context = daemon.DaemonContext(
            detach_process=False,  # We're doing this manually
        )

    def start(self):
        logger.info("Parent process ID: %d" % os.getpid())
        logger.info("Parent process group: %d" % os.getpgrp())
        logger.info('Starting daemon.')
        try:
            self._pid_file.acquire(timeout=0)
            with open(_PID_FILE_PATH, 'w') as f:
                f.write('%d' % self._pid_file.pid)
            logger.info('Lock file acquired.')

            logger.info('Performing double-fork.')
            if detach_process() > 0:
                logger.info("First fork's parent here, I'm returning.")
                return
            logger.info("Second fork's child here, I'm continuing.")

            with self._context:
                self.run()
        except Exception as e:
            logger.exception(e)
            raise
        finally:
            try:
                self._pid_file.release()
                logger.info('Lock file released.')
            except (lockfile.NotLocked, lockfile.NotMyLock):
                pass
        logger.info('Daemon is exiting.')

    def run(self):
        logger.info("I'm running!")
        logger.info("Daemon process ID: %d" % os.getpid())
        logger.info("Daemon process group: %d" % os.getpgrp())

    def get_pid(self):
        """
        Get PID of daemon process or ``None`` if daemon is not running.
        """
        with open(_PID_FILE_PATH) as f:
            return int(f.read())
