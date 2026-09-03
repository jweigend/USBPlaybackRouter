"""Backend tests against a real pw-dump of the reference setup (Mackie ProFX16v3,
rec-bus loopback in source mode, silent adapter links present)."""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usb_playback_router.backend import AMBIGUOUS, NO_SOURCE, NONE, OFFLINE, PAIR, RoutingBackend  # noqa: E402
from usb_playback_router.config import Config, DeviceDB  # noqa: E402
from usb_playback_router.discovery import choose_device, find_devices, signal_ports  # noqa: E402
from usb_playback_router.graph import LINK, Graph  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "profx16v3-source-mode.json")
PROFX = "alsa_output.usb-LOUD_Technologies_Inc._ProFx-00.analog-surround-40"
LB = "rec-bus-abhoere-out"


def objects():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def port_id(objs, node_name, port_name):
    nodes = {o["id"]: o["info"]["props"]["node.name"] for o in objs if o["type"].endswith("Node")}
    for o in objs:
        if o["type"].endswith("Port"):
            p = o["info"]["props"]
            if nodes.get(p["node.id"]) == node_name and p["port.name"] == port_name:
                return o["id"], p["node.id"]
    raise KeyError((node_name, port_name))


def without_links(objs, out_node=LB, in_node=PROFX):
    nodes = {o["id"]: o["info"]["props"]["node.name"] for o in objs if o["type"].endswith("Node")}
    return [o for o in objs if not (o["type"] == LINK
                                    and nodes.get(o["info"]["output-node-id"]) == out_node
                                    and nodes.get(o["info"]["input-node-id"]) == in_node)]


def with_link(objs, src, dst, lid):
    (op, on), (ip, inn) = port_id(objs, LB, src), port_id(objs, PROFX, dst)
    return objs + [{"id": lid, "type": LINK, "info": {"output-node-id": on, "output-port-id": op,
                                                      "input-node-id": inn, "input-port-id": ip}}]


def backend(source=LB, device="alsa_card.usb-LOUD_Technologies_Inc._ProFx-00"):
    cfg = Config(path="/nonexistent", device=device, source_node=source)
    return RoutingBackend(cfg, DeviceDB())


class ParsePositionsTest(unittest.TestCase):
    def test_both_spellings(self):
        from usb_playback_router.graph import parse_positions
        self.assertEqual(parse_positions("FL,FR,RL,RR"), ["FL", "FR", "RL", "RR"])
        self.assertEqual(parse_positions("[ RL RR ]"), ["RL", "RR"])
        self.assertEqual(parse_positions(["AUX0", "AUX1"]), ["AUX0", "AUX1"])
        self.assertEqual(parse_positions(None), [])


class ParseDumpTest(unittest.TestCase):
    def test_concatenated_arrays_with_removal(self):
        from usb_playback_router.graph import parse_dump
        text = ('[\n{"id": 1, "type": "PipeWire:Interface:Link", "info": {"a": 1}},\n'
                '{"id": 2, "type": "PipeWire:Interface:Link", "info": {"a": 2}}\n]\n'
                '[\n{"id": 1, "info": null}\n]\n'
                '[\n{"id": 3, "type": "PipeWire:Interface:Link", "info": {"a": 3}},\n'
                '{"id": 2, "type": "PipeWire:Interface:Link", "info": {"a": 22}}\n]\n')
        objs = parse_dump(text)
        self.assertEqual([o["id"] for o in objs], [2, 3])
        self.assertEqual(objs[0]["info"]["a"], 22)

    def test_fixture_parses(self):
        self.assertTrue(Graph.from_file(FIXTURE).alive)


class DiscoveryTest(unittest.TestCase):
    def test_device_and_pairs_from_port_order(self):
        g = Graph.from_objects(objects())
        devs = find_devices(g)
        d = choose_device(devs)
        self.assertEqual(d.node.name, PROFX)
        self.assertEqual(d.profile, "analog-surround-40")
        self.assertEqual([p.key for p in d.pairs], ["1/2", "3/4"])
        self.assertEqual([p.left.name for p in d.pairs], ["playback_FL", "playback_RL"])
        self.assertEqual([p.right.name for p in d.pairs], ["playback_FR", "playback_RR"])

    def test_auto_choice_prefers_multichannel_usb(self):
        g = Graph.from_objects(objects())
        self.assertEqual(choose_device(find_devices(g)).id, "alsa_card.usb-LOUD_Technologies_Inc._ProFx-00")

    def test_auto_choice_never_falls_back_to_a_stereo_card(self):
        objs = [o for o in objects() if not (o["type"].endswith("Node")
                                              and o["info"]["props"].get("node.name") == PROFX)]
        devs = find_devices(Graph.from_objects(objs))
        self.assertTrue(devs)                      # the onboard card is still there …
        self.assertIsNone(choose_device(devs))     # … but is not chosen automatically
        self.assertIsNotNone(choose_device(devs, "alsa_card.pci-0000_00_1b.0"))

    def test_auto_choice_is_pinned_for_the_process(self):
        b = backend(device="")
        self.assertEqual(b.read(Graph.from_objects(objects())).device.id,
                         "alsa_card.usb-LOUD_Technologies_Inc._ProFx-00")
        objs = [o for o in objects() if not (o["type"].endswith("Node")
                                              and o["info"]["props"].get("node.name") == PROFX)]
        st = b.read(Graph.from_objects(objs))
        self.assertEqual(st.code, OFFLINE)
        self.assertIn("ProFx", st.detail)

    def test_signal_ports_follow_negotiated_format(self):
        g = Graph.from_objects(objects())
        l, r = signal_ports(g.node_by_name(LB))
        self.assertEqual((l.name, r.name), ("output_RL", "output_RR"))

    def test_default_sink_from_metadata(self):
        g = Graph.from_objects(objects())
        self.assertEqual(g.default_sink_name(), "rec-bus")

    def test_device_db_labels(self):
        g = Graph.from_objects(objects())
        d = choose_device(find_devices(g))
        lab = backend().labels(d)
        self.assertEqual(lab.device_name(d), "Mackie ProFXv3")
        self.assertIn("Main Mix", lab.label(d.pairs[1]))


class StateTest(unittest.TestCase):
    def test_reference_state_is_3_4_despite_silent_links(self):
        st = backend().read(Graph.from_objects(objects()))
        self.assertEqual(st.code, PAIR)
        self.assertEqual(st.pair.key, "3/4")
        # the fixture contains WirePlumber's silent FL/FR links; they must not count
        self.assertEqual(sorted(st.linked), [2, 3])

    def test_no_links_is_none(self):
        st = backend().read(Graph.from_objects(without_links(objects())))
        self.assertEqual(st.code, NONE)

    def test_overdub_links_read_as_1_2(self):
        objs = without_links(objects())
        objs = with_link(objs, "output_RL", "playback_FL", 9001)
        objs = with_link(objs, "output_RR", "playback_FR", 9002)
        st = backend().read(Graph.from_objects(objs))
        self.assertEqual((st.code, st.pair.key), (PAIR, "1/2"))

    def test_both_pairs_is_ambiguous(self):
        objs = with_link(objects(), "output_RL", "playback_FL", 9001)
        objs = with_link(objs, "output_RR", "playback_FR", 9002)
        st = backend().read(Graph.from_objects(objs))
        self.assertEqual(st.code, AMBIGUOUS)

    def test_crossed_links_are_ambiguous(self):
        objs = without_links(objects())
        objs = with_link(objs, "output_RL", "playback_RR", 9001)
        objs = with_link(objs, "output_RR", "playback_RL", 9002)
        st = backend().read(Graph.from_objects(objs))
        self.assertEqual(st.code, AMBIGUOUS)

    def test_missing_source(self):
        st = backend(source="does-not-exist").read(Graph.from_objects(objects()))
        self.assertEqual(st.code, NO_SOURCE)

    def test_missing_device(self):
        objs = [o for o in objects() if not (o["type"].endswith("Node")
                                              and o["info"]["props"].get("node.name") == PROFX)]
        st = backend().read(Graph.from_objects(objs))
        self.assertEqual(st.code, OFFLINE)

    def test_pipewire_down(self):
        st = backend().read(Graph())
        self.assertEqual(st.code, OFFLINE)
        self.assertFalse(st.pipewire)

    def test_diag_mentions_silent_links(self):
        b = backend()
        text = b.diag(b.read(Graph.from_objects(objects())))
        self.assertIn("[silent]", text)
        self.assertIn("derived state: 3/4", text)


class SwitchTest(unittest.TestCase):
    """select_pair with pw-link replaced by a recorder and the graph replayed."""

    def test_select_removes_all_links_then_adds_two(self):
        b = backend()
        calls = []
        graphs = [Graph.from_objects(objects())]                      # before
        objs = without_links(objects())
        objs = with_link(objs, "output_RL", "playback_FL", 9001)
        objs = with_link(objs, "output_RR", "playback_FR", 9002)
        graphs.append(Graph.from_objects(objs))                       # after

        class R:
            returncode = 0
            stderr = ""
        b._pw_link = lambda *a: calls.append(a) or R()
        b.read = lambda graph=None: RoutingBackend.read(b, graphs.pop(0))
        ok, msg = b.select_pair("1/2")
        self.assertTrue(ok, msg)
        deletes = [c for c in calls if c[0] == "-d"]
        adds = [c for c in calls if c[0] != "-d"]
        self.assertEqual(len(deletes), 4)        # RL, RR and the two silent FL/FR links
        self.assertEqual(len(adds), 2)
        self.assertIn("Control Room", msg)


if __name__ == "__main__":
    unittest.main()
