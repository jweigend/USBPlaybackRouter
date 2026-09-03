"""Snapshot of the PipeWire graph, read with pw-dump.

Only the objects the router needs are kept: devices, nodes, ports, links and
the default-sink metadata. Everything is addressed by PipeWire object id
inside one snapshot; names are used only to find things.
"""
import json
import subprocess
from dataclasses import dataclass, field

NODE = "PipeWire:Interface:Node"
PORT = "PipeWire:Interface:Port"
LINK = "PipeWire:Interface:Link"
DEVICE = "PipeWire:Interface:Device"
METADATA = "PipeWire:Interface:Metadata"


@dataclass
class Port:
    id: int
    node_id: int
    index: int          # port.id — position of the port inside its node
    name: str
    direction: str      # "in" | "out"
    monitor: bool
    channel: str        # audio.channel, e.g. "FL"


@dataclass
class Node:
    id: int
    name: str
    props: dict
    positions: list = field(default_factory=list)   # negotiated format, e.g. ["RL", "RR"]
    ports: list = field(default_factory=list)        # all ports, sorted by index

    @property
    def description(self):
        return self.props.get("node.description") or self.props.get("node.nick") or self.name

    def inputs(self):
        return [p for p in self.ports if p.direction == "in" and not p.monitor]

    def outputs(self):
        return [p for p in self.ports if p.direction == "out" and not p.monitor]

    def port_named(self, name):
        for p in self.ports:
            if p.name == name:
                return p
        return None

    @property
    def declared_positions(self):
        pos = self.props.get("audio.position")
        if isinstance(pos, str):
            return [x.strip() for x in pos.split(",") if x.strip()]
        return list(pos or [])


@dataclass
class Link:
    id: int
    out_node: int
    out_port: int
    in_node: int
    in_port: int


@dataclass
class Device:
    id: int
    name: str
    props: dict
    profiles: list = field(default_factory=list)     # names of available profiles
    active_profile: str = ""

    @property
    def description(self):
        return self.props.get("device.description") or self.props.get("device.nick") or self.name


def parse_dump(text):
    """Parse pw-dump output into a list of objects.

    When the graph changes while pw-dump runs, its output is not one JSON
    array but several in a row: the dump plus one array per change, in which
    an object with "info": null means "removed". Later arrays win."""
    decoder = json.JSONDecoder()
    pos, n = 0, len(text)
    objects, order = {}, []
    while True:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n:
            break
        chunk, pos = decoder.raw_decode(text, pos)
        for o in chunk if isinstance(chunk, list) else [chunk]:
            oid = o.get("id")
            if o.get("info", 0) is None and "type" not in o:
                objects.pop(oid, None)
                continue
            if oid not in objects:
                order.append(oid)
            objects[oid] = o
    return [objects[i] for i in order if i in objects]


class Graph:
    """One consistent view of the graph. `alive` is False when pw-dump failed,
    which almost always means PipeWire is not running."""

    def __init__(self):
        self.alive = False
        self.nodes = {}
        self.ports = {}
        self.links = []
        self.devices = {}
        self.metadata = {}       # key -> value for the "default" metadata

    # ------------------------------------------------------------ reading

    @classmethod
    def read(cls, timeout=5):
        try:
            out = subprocess.run(["pw-dump", "-N"], capture_output=True, text=True,
                                 timeout=timeout, check=True).stdout
            objects = parse_dump(out)
        except (OSError, subprocess.SubprocessError, ValueError):
            return cls()
        return cls.from_objects(objects)

    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls.from_objects(parse_dump(f.read()))

    @classmethod
    def from_objects(cls, objects):
        g = cls()
        g.alive = True
        for o in objects:
            typ = o.get("type")
            info = o.get("info") or {}
            props = info.get("props") or {}
            params = info.get("params") or {}
            oid = o.get("id")
            if typ == NODE:
                positions = []
                for fmt in params.get("Format") or []:
                    positions = fmt.get("position") or positions
                g.nodes[oid] = Node(oid, props.get("node.name", ""), props, positions)
            elif typ == PORT:
                g.ports[oid] = Port(oid, props.get("node.id"), int(props.get("port.id", 0)),
                                    props.get("port.name", ""), props.get("port.direction", ""),
                                    bool(props.get("port.monitor", False)),
                                    props.get("audio.channel", ""))
            elif typ == LINK:
                g.links.append(Link(oid, info.get("output-node-id"), info.get("output-port-id"),
                                    info.get("input-node-id"), info.get("input-port-id")))
            elif typ == DEVICE:
                profiles = [p.get("name") for p in params.get("EnumProfile") or []]
                active = ""
                for p in params.get("Profile") or []:
                    active = p.get("name") or active
                g.devices[oid] = Device(oid, props.get("device.name", ""), props, profiles, active)
            elif typ == METADATA and (o.get("props") or props).get("metadata.name") == "default":
                # metadata objects carry their props at top level, not under info
                for entry in o.get("metadata") or []:
                    g.metadata[entry.get("key")] = entry.get("value")
        for port in g.ports.values():
            node = g.nodes.get(port.node_id)
            if node is not None:
                node.ports.append(port)
        for node in g.nodes.values():
            node.ports.sort(key=lambda p: (p.index, p.name))
        return g

    # ------------------------------------------------------------ queries

    def node_by_name(self, name):
        for n in self.nodes.values():
            if n.name == name:
                return n
        return None

    def links_between(self, out_node, in_node):
        return [l for l in self.links if l.out_node == out_node.id and l.in_node == in_node.id]

    def default_sink_name(self):
        for key in ("default.configured.audio.sink", "default.audio.sink"):
            v = self.metadata.get(key)
            if isinstance(v, dict):
                return v.get("name")
            if isinstance(v, str):
                try:
                    return json.loads(v).get("name")
                except ValueError:
                    return v
        return None
