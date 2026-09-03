"""Desktop notifications over D-Bus (org.freedesktop.Notifications), no notify-send."""
from gi.repository import Gio, GLib

from . import APP_ID

_proxy = None
_last_id = 0


def notify(summary, body="", icon="", timeout_ms=3000):
    global _proxy, _last_id
    try:
        if _proxy is None:
            _proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
                "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications", None)
        args = GLib.Variant("(susssasa{sv}i)",
                            (APP_ID, _last_id, icon, summary, body, [], {}, timeout_ms))
        res = _proxy.call_sync("Notify", args, Gio.DBusCallFlags.NONE, 1000, None)
        _last_id = res.unpack()[0]
    except GLib.Error:
        _proxy = None
