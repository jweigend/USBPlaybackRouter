"""Desktop entries and orphan reaping (pure parts)."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usb_playback_router import autostart, session  # noqa: E402


class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(autostart, "AUTOSTART", os.path.join(self.tmp.name, "autostart", "x.desktop")),
            mock.patch.object(autostart, "APP_MENU", os.path.join(self.tmp.name, "applications", "x.desktop")),
            mock.patch.object(sys, "argv", ["/opt/checkout/usb-playback-router"]),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_enable_writes_both_entries_disable_removes_autostart_only(self):
        self.assertFalse(autostart.enabled())
        self.assertTrue(autostart.set_enabled(True))
        self.assertTrue(os.path.exists(autostart.AUTOSTART))
        self.assertTrue(os.path.exists(autostart.APP_MENU))
        with open(autostart.AUTOSTART, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Exec=/opt/checkout/usb-playback-router\n", text)
        self.assertIn("X-GNOME-Autostart-enabled=true", text)
        self.assertIn("Icon=" + autostart.ICON, text)
        with open(autostart.APP_MENU, encoding="utf-8") as f:
            self.assertNotIn("Autostart", f.read())
        self.assertFalse(autostart.set_enabled(False))
        self.assertFalse(os.path.exists(autostart.AUTOSTART))
        self.assertTrue(os.path.exists(autostart.APP_MENU))
        autostart.remove_all()
        self.assertFalse(os.path.exists(autostart.APP_MENU))

    def test_icon_is_shipped_with_the_package(self):
        self.assertTrue(os.path.exists(autostart.ICON))


class ReapOrphansTest(unittest.TestCase):
    def test_kills_only_matching_processes_of_this_user(self):
        calls = []

        class R:
            stdout = "4242\n4243\n"
        with mock.patch.object(session.subprocess, "run", return_value=R()) as run, \
             mock.patch.object(session.os, "kill", side_effect=lambda pid, sig: calls.append((pid, sig))), \
             mock.patch.object(session.Graph, "read", return_value=session.Graph()):
            n = session.reap_orphans(timeout=0)
        argv = run.call_args[0][0]
        self.assertEqual(argv[:3], ["pgrep", "-u", str(os.getuid())])
        self.assertIn("^pw-loopback -g usb-playback-router", argv[-1])
        self.assertEqual(n, 2)
        self.assertEqual(sorted(p for p, _ in calls), [4242, 4243])

    def test_no_orphans(self):
        class R:
            stdout = ""
        with mock.patch.object(session.subprocess, "run", return_value=R()):
            self.assertEqual(session.reap_orphans(), 0)


if __name__ == "__main__":
    unittest.main()
