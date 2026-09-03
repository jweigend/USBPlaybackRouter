"""Tray icon and menu (GTK 3; XApp.StatusIcon on Cinnamon, AppIndicator elsewhere)."""
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # noqa: E402

from . import APP_ID, __version__
from . import icons
from .backend import AMBIGUOUS, NONE, PAIR
from .monitor import GraphMonitor
from .notify import notify


def _status_icon(menu):
    """Returns (set_icon(path, tooltip), holder)."""
    try:
        gi.require_version("XApp", "1.0")
        from gi.repository import XApp
    except (ValueError, ImportError):
        XApp = None
    if XApp is not None:
        icon = XApp.StatusIcon()
        icon.set_name(APP_ID)
        icon.set_primary_menu(menu)
        icon.set_secondary_menu(menu)

        def set_icon(path, text):
            icon.set_icon_name(path)
            icon.set_tooltip_text(text)
        return set_icon, icon

    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    ind = AppIndicator3.Indicator.new(APP_ID, icons.icon_name(icons.offline_icon()),
                                      AppIndicator3.IndicatorCategory.HARDWARE)
    ind.set_icon_theme_path(icons.icon_dir())
    ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    ind.set_menu(menu)

    def set_icon(path, text):
        ind.set_icon_full(icons.icon_name(path), text)
        ind.set_title(text)
    return set_icon, ind


class Tray:
    def __init__(self, backend):
        self.backend = backend
        self.lock = False            # set radio items programmatically without switching
        self.last_key = None
        self.pair_keys = None
        self.radio = {}

        self.menu = Gtk.Menu()
        self.header = Gtk.MenuItem(label="…")
        self.header.set_sensitive(False)
        self.menu.append(self.header)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.pair_anchor = len(self.menu.get_children())   # pair items are inserted here
        self.menu.append(Gtk.SeparatorMenuItem())
        for label, cb in (("Refresh now", lambda *_: self.refresh(force=True)),
                          ("Device information…", lambda *_: self.show_diag()),
                          (f"About {APP_ID} {__version__}", lambda *_: self.show_about()),
                          ("Quit", lambda *_: Gtk.main_quit())):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", cb)
            self.menu.append(item)
        self.menu.show_all()

        self.set_icon, self._holder = _status_icon(self.menu)
        self.refresh(force=True)
        self.monitor = GraphMonitor(self.refresh)

    # ------------------------------------------------------------ menu

    def _rebuild_pairs(self, device):
        for item in self.radio.values():
            self.menu.remove(item)
        self.radio = {}
        if device is None:
            return
        lab = self.backend.labels(device)
        first = None
        for pos, pair in enumerate(device.pairs):
            item = Gtk.RadioMenuItem(label=lab.label(pair), group=first)
            first = first or item
            item.connect("toggled", self._chosen, pair.key)
            self.menu.insert(item, self.pair_anchor + pos)
            self.radio[pair.key] = item
        self.menu.show_all()

    def _chosen(self, item, key):
        if self.lock or not item.get_active():
            return
        ok, text = self.backend.select_pair(key)
        print(text, file=sys.stderr)
        st = self.backend.read()
        icon = icons.pair_icon(st.pair) if ok and st.pair else icons.warning_icon()
        notify("Desktop audio switched" if ok else "Switching failed", text, icon)
        self.refresh(force=True)

    # ------------------------------------------------------------ state

    def refresh(self, force=False):
        st = self.backend.read()
        keys = tuple(p.key for p in st.device.pairs) if st.device else ()
        if keys != self.pair_keys:
            self.pair_keys = keys
            self._rebuild_pairs(st.device)
            force = True
        key = (st.code, st.pair.key if st.pair else None, st.detail,
               st.source.id if st.source else None)
        if not force and key == self.last_key:
            return True
        self.last_key = key
        text = self.backend.headline(st)
        if st.code == PAIR:
            icon = icons.pair_icon(st.pair)
        elif st.code in (AMBIGUOUS, NONE):
            icon = icons.warning_icon()
        else:
            icon = icons.offline_icon()
        self.set_icon(icon, text)
        self.header.set_label(text)
        self.lock = True
        try:
            for k, item in self.radio.items():
                item.set_sensitive(st.ready)
                item.set_active(st.pair is not None and st.pair.key == k)
        finally:
            self.lock = False
        return True

    # ------------------------------------------------------------ dialogs

    def show_diag(self):
        text = self.backend.diag()
        dlg = Gtk.Dialog(title="Device information", modal=False)
        dlg.set_default_size(640, 420)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_monospace(True)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.add(view)
        dlg.get_content_area().pack_start(scroll, True, True, 0)
        copy = dlg.add_button("Copy", 1)
        dlg.add_button("Close", Gtk.ResponseType.CLOSE)

        def on_response(d, resp):
            if resp == 1:
                Gtk.Clipboard.get_default(d.get_display()).set_text(text, -1)
            else:
                d.destroy()
        dlg.connect("response", on_response)
        copy.set_tooltip_text("Copy to clipboard for a bug report")
        dlg.show_all()

    def show_about(self):
        dlg = Gtk.AboutDialog(program_name="USB Playback Router", version=__version__,
                              comments="Send Linux desktop audio to USB 1/2, 3/4, 5/6 … of a "
                                       "multichannel USB audio interface without a DAW or patch bay.",
                              website="https://github.com/jweigend/USBPlaybackRouter")
        dlg.connect("response", lambda d, _: d.destroy())
        dlg.show()

    def run(self):
        GLib.set_prgname(APP_ID)
        Gtk.main()
        self.monitor.stop()
