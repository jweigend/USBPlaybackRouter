"""Session mode: loopback command, default-sink restore plan, remembered pair,
state derivation with the router's own node, controller behaviour."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usb_playback_router import session, state  # noqa: E402
from usb_playback_router.backend import NO_SOURCE, PAIR, RoutingBackend  # noqa: E402
from usb_playback_router.config import Config, DeviceDB  # noqa: E402
from usb_playback_router.graph import Graph  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "profx16v3-source-mode.json")
LB = "rec-bus-abhoere-out"


def objects_with_own_node():
    """The reference dump with the loopback renamed to the router's own node."""
    with open(FIXTURE, encoding="utf-8") as f:
        objs = json.load(f)
    for o in objs:
        if o["type"].endswith("Node") and o["info"]["props"].get("node.name") == LB:
            o["info"]["props"]["node.name"] = session.OUT_NAME
    return objs


def backend():
    return RoutingBackend(Config(path="/nonexistent"), DeviceDB())


class CommandTest(unittest.TestCase):
    def test_loopback_command(self):
        argv = session.loopback_command("alsa_output.usb-X.analog-surround-40", ("RL", "RR"))
        self.assertEqual(argv[0], "pw-loopback")
        cap = argv[argv.index("--capture-props") + 1]
        play = argv[argv.index("--playback-props") + 1]
        self.assertIn('media.class = "Audio/Sink"', cap)
        self.assertIn(f'node.name = "{session.SINK_NAME}"', cap)
        self.assertIn("audio.position = [ FL FR ]", cap)
        self.assertIn(f'node.name = "{session.OUT_NAME}"', play)
        self.assertIn('target.object = "alsa_output.usb-X.analog-surround-40"', play)
        self.assertIn("audio.position = [ RL RR ]", play)
        self.assertIn("node.passive = true", play)

    def test_restore_plan(self):
        self.assertEqual(session.restore_plan("rec-bus"), ("set", "rec-bus"))
        self.assertEqual(session.restore_plan(session.SINK_NAME), ("clear", None))
        self.assertEqual(session.restore_plan(""), ("clear", None))
        self.assertEqual(session.restore_plan(None), ("clear", None))

    def test_configured_default_from_graph(self):
        g = Graph.from_objects(objects_with_own_node())
        self.assertEqual(session.configured_default(g), "rec-bus")


class StateFileTest(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "state.ini")
            self.assertEqual(state.load(path), {})
            state.save("alsa_card.usb-A", "3/4", path)
            state.save("alsa_card.usb-B", "5/6", path)
            state.save("alsa_card.usb-A", "1/2", path)
            self.assertEqual(state.load(path), {"alsa_card.usb-A": "1/2", "alsa_card.usb-B": "5/6"})


class SessionStateTest(unittest.TestCase):
    def test_session_mode_reads_own_node(self):
        b = backend()
        self.assertEqual(b.config.mode, "session")
        self.assertEqual(b.source_node_name, session.OUT_NAME)
        st = b.read(Graph.from_objects(objects_with_own_node()))
        self.assertEqual((st.code, st.pair.key), (PAIR, "3/4"))

    def test_session_mode_without_node(self):
        with open(FIXTURE, encoding="utf-8") as f:
            st = backend().read(Graph.from_objects(json.load(f)))
        self.assertEqual(st.code, NO_SOURCE)
        self.assertIn("start the tray", st.detail)


class FakeNode:
    def __init__(self):
        self.running = False
        self.calls = []

    def start(self, hw, positions):
        self.calls.append(("start", hw, tuple(positions)))
        self.running = True
        return True

    def stop(self):
        self.calls.append(("stop",))
        self.running = False

    def wait_until_present(self, timeout=3.0):
        return True


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.b = backend()
        self.selected = []
        self.b.select_pair = lambda key, remember=True: self.selected.append(key) or (True, "")
        self.c = session.SessionController(self.b, manage_default=False)
        self.c.node = FakeNode()
        self.tmp = tempfile.TemporaryDirectory()
        self.state_path = os.path.join(self.tmp.name, "state.ini")
        self.c.remembered_pair = lambda device: state.load(self.state_path).get(device.id)

    def tearDown(self):
        self.tmp.cleanup()

    def graph(self, with_node=True):
        objs = objects_with_own_node()
        if not with_node:
            objs = [o for o in objs if not (o["type"].endswith("Node")
                                            and o["info"]["props"].get("node.name") == session.OUT_NAME)]
        return Graph.from_objects(objs)

    def test_start_uses_remembered_pair_positions(self):
        st = self.b.read(self.graph(with_node=False))
        state.save(st.device.id, "3/4", self.state_path)
        self.assertTrue(self.c.observe(st))
        self.assertEqual(self.c.node.calls[-1], ("start", st.device.node.name, ("RL", "RR")))

    def test_start_without_memory_uses_first_pair(self):
        st = self.b.read(self.graph(with_node=False))
        self.assertTrue(self.c.observe(st))
        self.assertEqual(self.c.node.calls[-1][2], ("FL", "FR"))

    def test_verify_once_after_start_repairs_wrong_pair(self):
        st = self.b.read(self.graph(with_node=False))
        state.save(st.device.id, "1/2", self.state_path)       # remembered 1/2 …
        self.c.observe(st)                                      # … node started
        self.c.restart_after = 0
        st2 = self.b.read(self.graph())                         # … but graph says 3/4
        self.assertTrue(self.c.observe(st2))
        self.assertEqual(self.selected, ["1/2"])
        self.assertFalse(self.c.observe(st2))                   # only once; manual work is respected
        self.assertEqual(self.selected, ["1/2"])

    def test_device_gone_stops_node(self):
        st = self.b.read(self.graph(with_node=False))
        self.c.observe(st)
        self.assertTrue(self.c.node.running)
        gone = Graph.from_objects([o for o in objects_with_own_node()
                                   if not (o["type"].endswith("Node")
                                           and "ProFx" in o["info"]["props"].get("node.name", ""))])
        self.assertTrue(self.c.observe(self.b.read(gone)))
        self.assertFalse(self.c.node.running)

    def test_pipewire_down_is_ignored(self):
        self.assertFalse(self.c.observe(self.b.read(Graph())))


if __name__ == "__main__":
    unittest.main()
