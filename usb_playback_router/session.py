"""Session mode: the router owns the routing node.

The node is a `pw-loopback` child process whose capture side is a stereo
Audio/Sink (what applications play to) and whose playback side is a stream
targeting the hardware node with the channel positions of the chosen pair.
WirePlumber links the playback side by position, so a fresh node lands on the
right pair by itself; switching at runtime relinks with pw-link like source
mode does. The node lives exactly as long as the application.

Default sink handling: the sink becomes default.configured.audio.sink while
the application runs; the previous value is restored on exit.
"""
import json
import os
import signal
import subprocess
import time

from . import APP_ID
from . import state as state_file
from .graph import Graph

SINK_NAME = APP_ID                 # capture side, media.class Audio/Sink
OUT_NAME = APP_ID + ".out"         # playback side, the "source node" of the backend
SINK_DESCRIPTION = "USB Playback Router"
DEFAULT_KEY = "default.configured.audio.sink"


def _spa(props):
    """SPA JSON dict as pw-loopback expects it: { key = value ... }."""
    parts = []
    for k, v in props.items():
        if isinstance(v, (list, tuple)):
            v = "[ " + " ".join(v) + " ]"
        elif isinstance(v, bool):
            v = "true" if v else "false"
        else:
            v = json.dumps(str(v))
        parts.append(f"{k} = {v}")
    return "{ " + " ".join(parts) + " }"


def loopback_command(hw_node_name, positions=("FL", "FR"), description=SINK_DESCRIPTION):
    capture = {"media.class": "Audio/Sink", "node.name": SINK_NAME,
               "node.description": description, "audio.position": ["FL", "FR"],
               "monitor.channel-volumes": True}
    playback = {"node.name": OUT_NAME, "node.description": description + " (out)",
                "target.object": hw_node_name, "node.target": hw_node_name,
                "audio.position": list(positions), "node.passive": True,
                "node.dont-reconnect": True}
    return ["pw-loopback", "-g", APP_ID, "--capture-props", _spa(capture),
            "--playback-props", _spa(playback)]


def reap_orphans(timeout=3.0):
    """Kill pw-loopback processes of this user left behind by a crashed
    instance (they are children of the tray and survive a SIGKILL of it),
    then wait until their nodes are gone. Returns the number killed."""
    try:
        out = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", f"^pw-loopback -g {APP_ID}( |$)"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    pids = [int(x) for x in out.split() if x.isdigit() and int(x) != os.getpid()]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    if pids:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            g = Graph.read()
            if g.alive and g.node_by_name(OUT_NAME) is None and g.node_by_name(SINK_NAME) is None:
                break
            time.sleep(0.1)
    return len(pids)


class LoopbackNode:
    def __init__(self):
        self.proc = None
        self.positions = None
        self.hw_node = None

    def start(self, hw_node_name, positions):
        self.stop()
        reap_orphans()
        try:
            self.proc = subprocess.Popen(loopback_command(hw_node_name, positions),
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self.proc = None
            return False
        self.positions, self.hw_node = tuple(positions), hw_node_name
        return True

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                try:
                    self.proc.kill()
                except OSError:
                    pass
            self.proc = None

    def wait_until_present(self, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            g = Graph.read()
            if g.node_by_name(OUT_NAME) is not None and g.node_by_name(SINK_NAME) is not None:
                return g
            if not self.running:
                return None
            time.sleep(0.1)
        return None


# ---------------------------------------------------------------- default sink

def configured_default(graph):
    v = graph.metadata.get(DEFAULT_KEY)
    if isinstance(v, dict):
        return v.get("name")
    if isinstance(v, str):
        try:
            return json.loads(v).get("name")
        except ValueError:
            return v
    return None


def restore_plan(previous, own=SINK_NAME):
    """What to do on exit: ("set", name) restores the previous default,
    ("clear", None) lets the session manager pick when the previous default
    was our own node (leftover from a crash) or unknown."""
    if previous and previous != own:
        return ("set", previous)
    return ("clear", None)


def set_default_sink(name):
    return _pw_metadata("0", DEFAULT_KEY, json.dumps({"name": name}), "Spa:String:JSON")


def clear_default_sink():
    return _pw_metadata("-d", "0", DEFAULT_KEY)


def _pw_metadata(*args):
    try:
        return subprocess.run(["pw-metadata", *args], capture_output=True, text=True,
                              timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------- controller

class SessionController:
    """Owns the loopback node for the lifetime of the tray, follows the device
    across disconnects and reapplies the remembered pair."""

    def __init__(self, backend, manage_default=True):
        self.backend = backend
        self.manage_default = manage_default
        self.node = LoopbackNode()
        self.previous_default = None
        self.device_node_id = None       # hw node id the loopback was started for
        self.restart_after = 0.0         # rate limit for restarts
        self.verify_pending = False      # check the pair once after each start

    def remembered_pair(self, device):
        return state_file.load().get(device.id)

    def desired_pair(self, device):
        key = self.remembered_pair(device)
        return device.pair(key) if key else (device.pairs[0] if device.pairs else None)

    def start(self, graph=None):
        graph = graph or Graph.read()
        if self.manage_default and self.previous_default is None:
            self.previous_default = configured_default(graph) or ""
        st = self.backend.read(graph)
        if st.device is None:
            return False
        return self._start_for(st.device)

    def _start_for(self, device):
        pair = self.desired_pair(device)
        positions = (pair.left.channel or "FL", pair.right.channel or "FR") if pair else ("FL", "FR")
        if not self.node.start(device.node.name, positions):
            return False
        self.device_node_id = device.node.id
        self.restart_after = time.monotonic() + 2.0
        if self.node.wait_until_present() is None:
            return False
        if self.manage_default:
            set_default_sink(SINK_NAME)
        return True

    def observe(self, st):
        """Called after every refresh. Returns True if it changed the graph and
        the caller should re-read.

        Only two things happen here: the node follows the device (gone →
        stop, (re)appeared → fresh node on the remembered pair) and, once
        after each start, the result is verified and repaired. Beyond that the
        graph is left alone, so manual pw-link work is respected."""
        if not st.pipewire:
            return False
        now = time.monotonic()
        if st.device is None:
            if self.node.running:
                self.node.stop()            # device gone: no node, default sink falls back
                self.device_node_id = None
                return True
            return False
        if not self.node.running or st.device.node.id != self.device_node_id:
            if now < self.restart_after:
                return False
            ok = self._start_for(st.device)
            self.verify_pending = ok
            return ok
        if self.verify_pending and st.source is not None:
            self.verify_pending = False
            want = self.desired_pair(st.device)
            if want and (st.pair is None or st.pair.key != want.key):
                ok, _ = self.backend.select_pair(want.key, remember=False)
                return ok
        return False

    def stop(self):
        self.node.stop()
        if self.manage_default:
            action, name = restore_plan(self.previous_default)
            if action == "set":
                set_default_sink(name)
            else:
                clear_default_sink()
