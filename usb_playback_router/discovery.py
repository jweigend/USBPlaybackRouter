"""Device and stereo-pair discovery on top of a Graph snapshot.

Pairs are built from the order of the hardware node's playback ports, not
from channel position names: what the mixer has are USB channels 1 … N in
hardware order, and the position names depend on the card profile.
"""
from dataclasses import dataclass, field


@dataclass
class StereoPair:
    index: int          # 0-based
    left: object        # Port
    right: object       # Port

    @property
    def channels(self):
        return (2 * self.index + 1, 2 * self.index + 2)

    @property
    def key(self):
        a, b = self.channels
        return f"{a}/{b}"

    @property
    def generic_label(self):
        return f"USB {self.key}"


@dataclass
class AudioDevice:
    id: str             # stable: device.name
    name: str
    vendor: str
    product: str
    bus: str
    profile: str
    profiles: list
    node: object        # hardware sink Node
    playback_ports: list = field(default_factory=list)
    pairs: list = field(default_factory=list)

    @property
    def channels(self):
        return len(self.playback_ports)

    def pair(self, key):
        for p in self.pairs:
            if p.key == key:
                return p
        return None


def find_devices(graph):
    """All ALSA playback sinks, as AudioDevice, biggest channel count first."""
    result = []
    for node in graph.nodes.values():
        props = node.props
        if props.get("media.class") != "Audio/Sink":
            continue
        if props.get("api.alsa.pcm.stream") != "playback":
            continue
        dev = graph.devices.get(props.get("device.id"))
        dprops = dev.props if dev else {}
        ports = node.inputs()
        pairs = [StereoPair(i // 2, ports[i], ports[i + 1]) for i in range(0, len(ports) - 1, 2)]
        result.append(AudioDevice(
            id=dev.name if dev else node.name,
            name=(dev.description if dev else node.description),
            vendor=dprops.get("device.vendor.name", ""),
            product=dprops.get("device.product.name", ""),
            bus=dprops.get("device.bus", ""),
            profile=props.get("device.profile.name", "") or (dev.active_profile if dev else ""),
            profiles=list(dev.profiles) if dev else [],
            node=node,
            playback_ports=ports,
            pairs=pairs,
        ))
    result.sort(key=lambda d: (-d.channels, d.name))
    return result


def choose_device(devices, wanted=None):
    """Pick the device to manage. `wanted` matches device.name or node.name,
    exactly or as substring. Without it: the USB device with the most
    playback channels, preferring ones with more than one pair."""
    if wanted:
        for d in devices:
            if wanted in (d.id, d.node.name):
                return d
        for d in devices:
            if wanted in d.id or wanted in d.node.name or wanted in d.name:
                return d
        return None
    usb = [d for d in devices if d.bus == "usb"]
    for pool in (usb, devices):
        multi = [d for d in pool if len(d.pairs) > 1]
        if multi:
            return multi[0]
        if pool:
            return pool[0]
    return None


def signal_ports(node):
    """The two output ports of a stream node that actually carry signal.

    The adapter creates one output port per channel of the *target*, so a
    2-channel stream on a 4-channel sink has four output ports of which only
    the two matching the negotiated format carry audio. Order of preference:
    negotiated format, declared audio.position, then port order."""
    outs = node.outputs()
    by_channel = {p.channel: p for p in outs}
    by_name = {p.name: p for p in outs}
    for positions in (node.positions, node.declared_positions):
        if len(positions) >= 2:
            l, r = positions[0], positions[1]
            pl = by_channel.get(l) or by_name.get(f"output_{l}")
            pr = by_channel.get(r) or by_name.get(f"output_{r}")
            if pl and pr and pl is not pr:
                return pl, pr
    if len(outs) >= 2:
        return outs[0], outs[1]
    return None
