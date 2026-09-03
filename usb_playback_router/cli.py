"""Command line entry point."""
import fcntl
import os
import sys

from . import APP_ID, __version__
from .backend import PAIR, RoutingBackend

USAGE = f"""{APP_ID} {__version__} — choose the USB stereo pair that receives desktop audio

usage: {APP_ID} [command]

  (none) | tray     start the tray icon
  status            print the derived state; exit 0 only if exactly one pair is selected
  select PAIR       switch desktop audio to PAIR, e.g. "3/4"
  pairs             list the detected stereo pairs of the managed device
  diag              print diagnostic information for bug reports
  autostart on|off  start the tray at login (also adds an application-menu entry)
  autostart status
  uninstall         remove the autostart and application-menu entries
  -h | --help       this text

configuration: ~/.config/{APP_ID}.conf  (see README)
"""


def _single_instance():
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), f"{APP_ID}.lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return fd


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "tray"
    backend = RoutingBackend()

    if cmd == "status":
        st = backend.read()
        print(backend.headline(st))
        return 0 if st.code == PAIR else 1

    if cmd == "select":
        if len(argv) < 2:
            print("select: which pair? e.g. select 3/4", file=sys.stderr)
            return 2
        ok, text = backend.select_pair(argv[1].replace("-", "/"))
        print(text)
        return 0 if ok else 1

    if cmd == "pairs":
        st = backend.read()
        if st.device is None:
            print(backend.headline(st), file=sys.stderr)
            return 1
        lab = backend.labels(st.device)
        for p in st.device.pairs:
            mark = "*" if st.pair is not None and st.pair.key == p.key else " "
            print(f"{mark} {p.key:>5}  {lab.label(p)}")
        return 0

    if cmd == "diag":
        print(backend.diag())
        return 0

    if cmd == "autostart":
        from . import autostart
        arg = argv[1] if len(argv) > 1 else "status"
        if arg in ("on", "off"):
            autostart.set_enabled(arg == "on")
        elif arg != "status":
            print("autostart: on, off or status", file=sys.stderr)
            return 2
        print("autostart: " + ("on" if autostart.enabled() else "off"))
        return 0

    if cmd == "uninstall":
        from . import autostart
        autostart.remove_all()
        print("removed autostart and application-menu entries")
        return 0

    if cmd == "tray":
        if _single_instance() is None:
            print(f"{APP_ID} is already running.", file=sys.stderr)
            return 0
        try:
            from .tray import Tray
        except SystemExit as e:
            print(e, file=sys.stderr)
            return 1
        Tray(backend).run()
        return 0

    print(USAGE.strip())
    return 0 if cmd in ("-h", "--help", "help") else 2


if __name__ == "__main__":
    sys.exit(main())
