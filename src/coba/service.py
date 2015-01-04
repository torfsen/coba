#!/usr/bin/env python

"""
The coba background daemon.
"""

import errno
import logging
import logging.handlers
import os
import signal
import socket
import sys
import time

from daemon import DaemonContext
import lockfile.pidlockfile
import setproctitle


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
        os._exit(os.EX_OK)
    return False


class PIDFile(lockfile.pidlockfile.PIDLockFile):
    """
    A locked PID file.

    This is basically ``locakfile.pidlockfile.PIDLockfile``, with the
    small modification that the PID is obtained only when the lock is
    acquired. This makes sure that the PID in the PID file is always
    that of the process that actually acquired the lock (even if the
    instance was created in another process, for example before
    forking).
    """
    def __init__(self, *args, **kwargs):
        lockfile.pidlockfile.PIDLockFile.__init__(self, *args, **kwargs)
        self.pid = None

    def acquire(self, *args, **kwargs):
        self.pid = os.getpid()
        return lockfile.pidlockfile.PIDLockFile.acquire(self, *args, **kwargs)


class Service(object):
    """
    A background service.

    This class provides the basic framework for running and controlling
    a background daemon. This includes methods for starting the daemon
    (including things like proper setup of a detached deamon process),
    checking whether the daemon is running, asking the daemon to
    terminate and for killing the daemon should that become necessary.

    The class has a dual interface: Some of the methods are intended to
    be called from the controlling process while others run in the
    daemon process. The control methods are:

    * ``start`` to start the daemon
    * ``stop`` to ask the daemon to stop
    * ``kill`` to kill the daemon
    * ``is_running`` to check whether the daemon is running
    * ``get_pid`` to get the daemon's process ID

    Subclasses usually do not need to override any of these.

    The daemon methods are ``run`` and ``on_terminate``. Subclasses
    should at least override the ``run`` method to provide the major
    daemon functionality. You may also want to provide a custom
    implementation of ``on_terminate`` which is called when the daemon
    receives a SIGTERM signal (for example after ``stop`` was called).

    The daemon can use its ``logger`` attribute to log messages to
    syslog. Uncaught exceptions that occur while the daemon is running
    are automatically logged that way.
    """

    def __init__(self, name):
        """
        Constructor.

        ``name`` is a string that identifies the daemon. The name is
        used for the name of the daemon process, the PID file and for
        the messages to syslog.
        """
        self.name = name
        # FIXME: PID files go into ``/var/run`` by convention. However,
        # writing there requires root privileges. What's the right
        # thing to do?
        self.pid_file = PIDFile(os.path.join('/tmp', name + '.pid'))

        self.logger = logging.getLogger(name)
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        format_str = '%(name)s: <%(levelname)s> %(message)s'
        handler.setFormatter(logging.Formatter(format_str))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    def is_running(self):
        """
        Check if the daemon is running.
        """
        return self.get_pid() is not None

    def get_pid(self):
        """
        Get PID of daemon process or ``None`` if daemon is not running.
        """
        return self.pid_file.read_pid()

    def stop(self):
        """
        Tell the daemon process to stop.

        Sends the SIGTERM signal to the daemon process, requesting it
        to terminate. A
        """
        pid = self.get_pid()
        if not pid:
            raise ValueError('Daemon is not running.')
        os.kill(pid, signal.SIGTERM)

    def kill(self):
        """
        Kill the daemon process.

        Sends the SIGKILL signal to the daemon process, killing it. You
        probably want to try ``stop`` first.

        After the process is killed its PID file is removed.
        """
        pid = self.get_pid()
        if not pid:
            raise ValueError('Daemon is not running.')
        os.kill(pid, signal.SIGKILL)
        self.pid_file.break_lock()

    def start(self):
        """
        Start the daemon process.

        The daemon process is started in the background and the calling
        process returns.

        Once the daemon process is initialized it calls the ``run``
        method.
        """
        pid = self.get_pid()
        if pid:
            raise ValueError('Daemon is already running at PID %d.' % pid)

        if detach_process():
            # Calling process returns
            return
        # Daemon process continues here

        setproctitle.setproctitle(self.name)

        def terminator(signum, frame):
            try:
                self.on_terminate()
            except Exception as e:
                self.logger.exception(e)
            sys.exit()

        try:
            self.pid_file.acquire(timeout=0)
            with DaemonContext(
                    detach_process=False,
                    signal_map={
                        signal.SIGTTIN: None,
                        signal.SIGTTOU: None,
                        signal.SIGTSTP: None,
                        signal.SIGTERM: terminator,
                    }):
                self.run()
        except Exception as e:
            self.logger.exception(e)
        finally:
            try:
                self.pid_file.release()
            except Exception as e:
                self.logger.exception(e)

        # We need to shutdown the daemon process at this point, because
        # otherwise it will continue executing from after the original
        # call to ``start``.
        sys.exit()

    def run(self):
        """
        Main daemon method.

        This method is called once the daemon is initialized and
        running. Subclasses should override this method and provide the
        implementation of the daemon's functionality. The default
        implementation does nothing and immediately returns.

        Once this method returns the daemon process automatically exits.
        Typical implementations therefore contain some kind of loop.

        The daemon may also be terminated by sending it the SIGTERM
        signal. In that case ``on_terminate`` will be called and should
        make the loop in ``run`` terminate (for example via one of the
        communication methods provided by the ``threading`` module).
        """
        pass

    def on_terminate(self):
        """
        Called when daemon receives signal to terminate.

        This method is automatically called when the daemon receives
        the SIGTERM signal, telling it to terminate. The call is done
        via Python's signalling mechanisms, see the ``signal`` module
        for details. Most importantly, the call is asynchronous.

        A subclass's implementation should stop the daemon's work and
        perform the necessary cleanup. The actual shutdown of the
        daemon process is done automatically once this method exits.

        The default implementation does nothing and returns immediately.

        Note that this method is not automatically called when the
        daemon's ``run`` method exits.
        """
        pass

