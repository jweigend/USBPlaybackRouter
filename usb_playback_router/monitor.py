"""Follow graph changes with `pw-dump -m` instead of polling.

pw-dump -m prints every added, changed or removed object as JSON. The router
does not merge these incrementally; it uses them as a trigger and re-reads the
whole graph after a short debounce. If the monitor process dies (PipeWire
restart), a slow poll takes over and tries to restart it.
"""
import os
import subprocess

from gi.repository import GLib

DEBOUNCE_MS = 150
FALLBACK_POLL_MS = 3000


class GraphMonitor:
    def __init__(self, callback):
        self.callback = callback
        self.proc = None
        self._debounce = None
        self._poll = None
        self.start()

    def start(self):
        try:
            self.proc = subprocess.Popen(["pw-dump", "-m", "-N"], stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL)
        except OSError:
            self.proc = None
            self._start_poll()
            return
        fd = self.proc.stdout.fileno()
        os.set_blocking(fd, False)
        GLib.io_add_watch(fd, GLib.PRIORITY_DEFAULT, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._on_io)
        if self._poll is not None:
            GLib.source_remove(self._poll)
            self._poll = None

    def _on_io(self, fd, cond):
        if cond & GLib.IO_IN:
            try:
                while os.read(fd, 65536):
                    pass
            except BlockingIOError:
                pass
            except OSError:
                cond |= GLib.IO_HUP
            self._schedule()
        if cond & (GLib.IO_HUP | GLib.IO_ERR):
            self._reap()
            self._start_poll()
            return False
        return True

    def _schedule(self):
        if self._debounce is not None:
            GLib.source_remove(self._debounce)
        self._debounce = GLib.timeout_add(DEBOUNCE_MS, self._fire)

    def _fire(self):
        self._debounce = None
        self.callback()
        return False

    def _start_poll(self):
        if self._poll is None:
            self._poll = GLib.timeout_add(FALLBACK_POLL_MS, self._poll_tick)

    def _poll_tick(self):
        self.callback()
        # try to get the monitor back; start() removes the poll on success
        self.start()
        return self._poll is not None

    def _reap(self):
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=1)
            except (OSError, subprocess.SubprocessError):
                pass
            self.proc = None

    def stop(self):
        self._reap()
