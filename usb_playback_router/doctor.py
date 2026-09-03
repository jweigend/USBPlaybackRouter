"""`check`: are the system packages there? Prints what is missing and the
apt command for it. Nothing is installed; that needs root and differs per
distribution."""
import os
import shutil
import subprocess

PW_TOOLS = ("pw-dump", "pw-link", "pw-loopback", "pw-metadata")


def _typelib(namespace, version):
    try:
        import gi
        gi.require_version(namespace, version)
        return True
    except (ImportError, ValueError):
        return False


def tray_package(desktop=None):
    """The tray package that fits the desktop: XApp on Cinnamon, AppIndicator
    elsewhere."""
    desktop = (desktop if desktop is not None else os.environ.get("XDG_CURRENT_DESKTOP", "")).lower()
    return "gir1.2-xapp-1.0" if "cinnamon" in desktop else "gir1.2-ayatanaappindicator3-0.1"


def pipewire_version():
    try:
        out = subprocess.run(["pw-dump", "--version"], capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if "Compiled with libpipewire" in line or "Linked with libpipewire" in line:
                return line.split()[-1]
        return out.split()[-1] if out.split() else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def checks():
    """List of (ok, description, package or None)."""
    result = []
    missing_tools = [t for t in PW_TOOLS if shutil.which(t) is None]
    if missing_tools:
        result.append((False, "PipeWire tools: " + ", ".join(missing_tools) + " missing", "pipewire-bin"))
    else:
        result.append((True, f"PipeWire tools (libpipewire {pipewire_version() or '?'})", "pipewire-bin"))
    try:
        import gi  # noqa: F401
        result.append((True, "PyGObject", "python3-gi"))
    except ImportError:
        result.append((False, "PyGObject missing", "python3-gi"))
        gi = None
    result.append((_typelib("Gtk", "3.0"), "GTK 3 bindings", "gir1.2-gtk-3.0"))
    xapp = _typelib("XApp", "1.0")
    appind = _typelib("AyatanaAppIndicator3", "0.1")
    if xapp or appind:
        result.append((True, "tray backend: " + ("XApp" if xapp else "AppIndicator"), None))
    else:
        result.append((False, "no tray backend", tray_package()))
    return result


def apt_line(results):
    packages = [pkg for ok, _, pkg in results if not ok and pkg]
    if not packages:
        return ""
    tool = "apt install" if shutil.which("apt-get") else "install the equivalent of"
    return f"sudo {tool} " + " ".join(packages) if tool.startswith("apt") else f"{tool}: " + " ".join(packages)


def report():
    """Print the check, return the exit code (0 = all there)."""
    results = checks()
    for ok, text, _ in results:
        print(("ok       " if ok else "missing  ") + text)
    line = apt_line(results)
    if line:
        print("\nTo fix: " + line)
        return 1
    return 0
