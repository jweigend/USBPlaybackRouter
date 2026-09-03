"""Routing backend: derives the state from the graph and switches pairs.

Source mode (milestone 0): an existing node — typically the playback side of
a loopback — feeds the hardware. The backend relinks that node's two
signal-carrying outputs to the selected hardware pair. It never touches the
default sink, never writes configuration and never removes links of other
clients.

Session mode: the source node is the playback side of the router's own
loopback (see session.py); switching and state derivation are the same.
"""
import subprocess
from dataclasses import dataclass

from . import __version__
from . import state as state_file
from .config import Config, DeviceDB, Labels
from .discovery import choose_device, find_devices, signal_ports
from .graph import Graph
from .session import OUT_NAME

OFFLINE = "offline"          # device not present, or PipeWire not running
NO_SOURCE = "no-source"      # device present, source node missing
NONE = "none"                # source present, no signal-carrying link to the device
AMBIGUOUS = "ambiguous"      # links to more than one pair, or crossed links
PAIR = "pair"                # exactly one pair


@dataclass
class Status:
    code: str
    graph: object = None
    device: object = None      # AudioDevice
    source: object = None      # Node
    signal: tuple = None       # (Port, Port)
    pair: object = None        # StereoPair
    linked: dict = None        # hw port index -> set of source port names (signal ports only)
    detail: str = ""

    @property
    def ready(self):
        return self.device is not None and self.source is not None and self.signal is not None

    @property
    def pipewire(self):
        return self.graph is not None and self.graph.alive


class RoutingBackend:
    def __init__(self, config=None, db=None):
        self.config = config or Config.load()
        self.db = db or DeviceDB()
        self.pinned = None      # auto-chosen device id, kept for the process lifetime

    def labels(self, device):
        return Labels(self.config, self.db, device)

    @property
    def source_node_name(self):
        return self.config.source_node if self.config.mode == "source" else OUT_NAME

    # ------------------------------------------------------------ state

    def read(self, graph=None):
        graph = graph or Graph.read()
        if not graph.alive:
            return Status(OFFLINE, graph, detail="PipeWire is not running")
        wanted = self.config.device or self.pinned
        device = choose_device(find_devices(graph), wanted)
        if device is None:
            detail = f"'{wanted}' not connected" if wanted else "no multichannel USB audio device found"
            return Status(OFFLINE, graph, detail=detail)
        if not self.config.device:
            self.pinned = device.id
        source = graph.node_by_name(self.source_node_name)
        if source is None:
            if self.config.mode == "source":
                detail = f"source node '{self.source_node_name}' not found"
            else:
                detail = "routing node not running — start the tray"
            return Status(NO_SOURCE, graph, device, detail=detail)
        signal = signal_ports(source)
        if signal is None:
            return Status(NO_SOURCE, graph, device, source,
                          detail=f"source node '{source.name}' has no stereo output")
        return self._derive(graph, device, source, signal)

    def _derive(self, graph, device, source, signal):
        left, right = signal
        index_of = {p.id: i for i, p in enumerate(device.playback_ports)}
        linked = {}
        for l in graph.links_between(source, device.node):
            if l.out_port not in (left.id, right.id) or l.in_port not in index_of:
                continue
            name = "L" if l.out_port == left.id else "R"
            linked.setdefault(index_of[l.in_port], set()).add(name)
        st = Status(PAIR, graph, device, source, signal, linked=linked)
        if not linked:
            st.code = NONE
            return st
        hits = [p for p in device.pairs
                if linked.get(2 * p.index) == {"L"} and linked.get(2 * p.index + 1) == {"R"}]
        touched = set(linked)
        if len(hits) == 1 and touched == {2 * hits[0].index, 2 * hits[0].index + 1}:
            st.pair = hits[0]
        else:
            st.code = AMBIGUOUS
        return st

    def headline(self, st):
        lab = self.labels(st.device)
        if not st.pipewire:
            return "PipeWire is not running"
        if st.code == OFFLINE:
            return f"USB audio device not connected ({st.detail})" if st.detail else "USB audio device not connected"
        if st.code == NO_SOURCE:
            return f"{lab.device_name(st.device)}: {st.detail}"
        if st.code == PAIR:
            return f"Desktop audio → {lab.label(st.pair)}"
        if st.code == AMBIGUOUS:
            return "Desktop audio reaches more than one pair — please select one"
        return "Desktop audio is not linked to the device — please select a pair"

    # ------------------------------------------------------------ switching

    def select_pair(self, key, remember=True):
        """Switch to pair `key` (e.g. "3/4"). Returns (ok, message).
        In session mode the choice is remembered per device so the node can be
        recreated on the same pair after a reconnect."""
        st = self.read()
        if not st.ready:
            return False, self.headline(st)
        pair = st.device.pair(key)
        if pair is None:
            keys = ", ".join(p.key for p in st.device.pairs)
            return False, f"unknown pair '{key}' — available: {keys}"
        # 1. every link from the source node to the device, signal ports or not
        for l in st.graph.links_between(st.source, st.device.node):
            self._pw_link("-d", str(l.id))
        # 2. exactly two new ones
        errors = []
        for src, dst in zip(st.signal, (pair.left, pair.right)):
            res = self._pw_link(str(src.id), str(dst.id))
            if res.returncode != 0:
                errors.append(f"{st.source.name}:{src.name} → {dst.name}: {res.stderr.strip()}")
        if errors:
            return False, "linking failed: " + "; ".join(errors)
        # 3. verify against the graph
        after = self.read()
        lab = self.labels(after.device)
        if after.code == PAIR and after.pair.key == key:
            if remember and self.config.mode == "session":
                state_file.save(st.device.id, key)
            hint = lab.hint(pair)
            return True, f"Desktop audio → {lab.label(pair)}." + (f" {hint}" if hint else "")
        return False, f"switched, but the graph now reads: {self.headline(after)}"

    @staticmethod
    def _pw_link(*args):
        return subprocess.run(["pw-link", *args], capture_output=True, text=True)

    # ------------------------------------------------------------ diagnostics

    def diag(self, st=None):
        st = st or self.read()
        lines = [f"usb-playback-router {__version__}", f"mode: {self.config.mode}",
                 f"config: {self.config.path}", ""]
        if not st.pipewire:
            lines.append("PipeWire: not running")
            return "\n".join(lines)
        d = st.device
        if d is None:
            lines.append("device: none found")
            devs = find_devices(st.graph)
            for x in devs:
                lines.append(f"  candidate: {x.id} ({x.channels} ch, {x.bus})")
            return "\n".join(lines)
        lab = self.labels(d)
        lines += [f"device: {lab.device_name(d)}",
                  f"  vendor/product: {d.vendor} / {d.product}",
                  f"  device.name: {d.id}",
                  f"  node.name: {d.node.name}",
                  f"  profile: {d.profile}  (available: {', '.join(d.profiles)})",
                  f"  playback channels: {d.channels}  ({', '.join(p.channel for p in d.playback_ports)})",
                  "pairs:"]
        for p in d.pairs:
            lines.append(f"  {p.key:>5}  {p.left.name}, {p.right.name}  — {lab.label(p)}")
        lines.append(f"source node: {st.source.name if st.source else '(missing)'}")
        if st.source:
            lines.append(f"  negotiated positions: {', '.join(st.source.positions) or '(none)'}")
            lines.append(f"  output ports: {', '.join(p.name for p in st.source.outputs())}")
        if st.signal:
            lines.append(f"  signal ports: {st.signal[0].name}, {st.signal[1].name}")
        if st.source and d:
            for l in st.graph.links_between(st.source, d.node):
                o = st.graph.ports.get(l.out_port); i = st.graph.ports.get(l.in_port)
                sig = "signal" if st.signal and o and o.id in (st.signal[0].id, st.signal[1].id) else "silent"
                lines.append(f"  link {l.id}: {o.name if o else '?'} → {i.name if i else '?'}  [{sig}]")
        lines.append(f"default sink: {st.graph.default_sink_name()}")
        lines.append(f"derived state: {st.pair.key if st.pair else st.code}")
        if st.detail:
            lines.append(f"detail: {st.detail}")
        return "\n".join(lines)
