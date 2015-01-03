#!/usr/bin/env python


import errno
import logging
import logging.handlers
import os
import time

from daemon import DaemonContext
import lockfile.pidlockfile


_NAME = 'coba-daemon'


logger = logging.getLogger(_NAME)
_handler = logging.handlers.SysLogHandler(address='/dev/log')
_format = '%(name)s: <%(levelname)s> %(message)s'
_handler.setFormatter(logging.Formatter(_format))
logger.addHandler(_handler)
logger.setLevel(logging.DEBUG)

def log(msg):
    logger.info('(%d) %s' % (os.getpid(), msg))


def detach_process():
    """
    Detach daemon process.

    Forks the current process into a parent and a detached child. The
    child process resides in its own process group, has no controlling
    terminal attached and is cleaned up by the init process.

    Returns ``True`` for the parent and ``False`` for the child.
    """
    # To detach from our process group we need to call ``setsid``. We
    # can only do that if we aren't a process group leader. Therefore
    # we fork once, which makes sure that the new child process is not
    # a process group leader.
    pid = os.fork()
    if pid > 0:
        # Parent process
        return True
    os.setsid()
    # We now fork a second time and let the second's fork parent exit.
    # This makes the second fork's child process an orphan. Orphans are
    # cleaned up by the init process, so we won't end up with a zombie.
    # In addition, the second fork's child is no longer a session
    # leader and can therefore never acquire a controlling terminal.
    pid = os.fork()
    if pid > 0:
        log("Second fork's parent here, I'm exiting.")
        os._exit(os.EX_OK)
    return False


class PIDFile(lockfile.pidlockfile.PIDLockFile):

    def __init__(self, *args, **kwargs):
        lockfile.pidlockfile.PIDLockFile.__init__(self, *args, **kwargs)
        self.pid = None

    def acquire(self, *args, **kwargs):
        self.pid = os.getpid()
        return lockfile.pidlockfile.PIDLockFile.acquire(self, *args, **kwargs)



class Daemon(object):

    def _start(self, pid_file_path):
        log('Performing double-fork.')

        if detach_process():
            log("First fork's parent here, I'm returning.")
            return

        log("Second fork's child here, I'm continuing.")
        pid_file = PIDFile(pid_file_path)

        try:
            pid_file.acquire(timeout=0)
            log('Lock file acquired.')
            with DaemonContext(detach_process=False):
                log('Executing daemon code.')
                self.run()
        except Exception as e:
            logger.exception(e)
        finally:
            try:
                pid_file.release()
                log('Lock file released.')
            except Exception as e:
                logger.exception(e)

        # We need to shutdown the daemon process at this point, because
        # otherwise it will continue executing from after the original
        # call to ``DaemonController.start``.
        log('Daemon is exiting.')
        os._exit(os.EX_OK)

    def run(self):
        log('This is the run method.')
        time.sleep(5)


class DaemonController(object):

    def __init__(self, daemon, pid_file_path):
        self._daemon = daemon
        self._pid_file = PIDFile(pid_file_path)

    def start(self):
        logger.info('******************************************')
        pid = self.get_pid()
        if pid:
            log('ERROR: Daemon is already running at PID %d.' % pid)
            raise ValueError('Daemon is already running at PID %d.' % pid)
        log('Starting daemon.')
        self._daemon._start(self._pid_file.path)

    def is_running(self):
        return self.get_pid() is not None

    def call(self, fun, *args):
        if not self.is_running():
            raise ValueError('Daemon is not running.')
        raise NotImplementedError()

    def get_pid(self):
        """
        Get PID of daemon process or ``None`` if daemon is not running.
        """
        return self._pid_file.read_pid()

