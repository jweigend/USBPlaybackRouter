# <img src="usb_playback_router/icon.svg" width="32" height="32" alt=""> USB Playback Router

**Send Linux desktop audio to USB 1/2, 3/4, 5/6 … of a multichannel USB
audio interface without opening a DAW or patch bay.**

Many USB mixers (Mackie ProFXv3, PreSonus ARc, Allen & Heath ZEDi, …) expose
more than one stereo return pair from the computer. Linux shows them as one
"Surround 4.0" device and plays everything to the first pair. This tray icon
shows which pair desktop audio reaches and switches it with one click.

Concept and design: [usb-playback-router-concept.md](usb-playback-router-concept.md).

## Status

Milestone 1. Two modes, same switching and state code:

- **Session mode** (default, no configuration needed): the tool creates a
  stereo routing sink with `pw-loopback`, makes it the default sink and links
  it to the chosen hardware pair. The node lives as long as the tray; the
  chosen pair is remembered per device and reapplied after a reconnect. The
  previous default sink is restored on exit. Verified on the Mackie
  ProFX16v3 with a measured test signal on all four channels, including a
  simulated unplug/reconnect (card profile off and on).
- **Source mode**: an existing loopback feeds the mixer and the tool only
  relinks it. Verified on the reference setup (Mackie ProFX16v3 with
  `50-rec-bus.conf`), where it replaced a device-specific predecessor.

Not yet: routing without the tray running (a generated PipeWire drop-in),
device picker for several multichannel interfaces.

## Requirements

| | |
|---|---|
| backend | `pipewire-bin` (`pw-dump`, `pw-link`, `pw-loopback`, `pw-metadata`), PipeWire ≥ 0.3.60 |
| UI | Python ≥ 3.11, `python3-gi`, `gir1.2-gtk-3.0` |
| tray | `gir1.2-xapp-1.0` (Cinnamon) or `gir1.2-ayatanaappindicator3-0.1` |

No pip packages, no library binding to PipeWire or WirePlumber. WirePlumber
(or pipewire-media-session) only has to be running, any version. Tested with
PipeWire 1.0.5 and WirePlumber 0.4.17 on Linux Mint 22.

## Installation

```bash
sudo apt install pipewire-bin python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
pipx install git+https://github.com/jweigend/USBPlaybackRouter
usb-playback-router autostart on      # tray at login + application-menu entry
usb-playback-router &                 # start it now
```

`pipx` must see the system GTK bindings; if the tray complains about
missing `gi`, use `pipx install --system-site-packages …`. From a checkout,
`./install.sh` does the same with a symlink instead of pipx.

## Configuration

None is needed for session mode: the tool picks the USB interface with more
than one stereo pair. A plain stereo card is never chosen automatically, so
unplugging the mixer shows as offline instead of moving audio to the built-in
card.

`~/.config/usb-playback-router.conf`:

```ini
[device]
name = alsa_card.usb-LOUD_Technologies_Inc._ProFx-00   ; optional; forces a device, also a stereo one

[source]
node = rec-bus-abhoere-out     ; source mode: relink this node's outputs to the chosen pair

[labels]                       ; optional, per pair
3/4 = USB 3/4 – channel strip 15/16 → Main Mix

[hints]                        ; shown in the notification after switching
1/2 = Mute channel strip 15/16 on the mixer!
```

**Source mode** is for setups that already have a virtual sink and a loopback
feeding the mixer (see `50-rec-bus.conf` in the reference setup). The tool
then only moves the two signal-carrying outputs of the loopback to the
selected hardware pair. It never touches the default sink, never writes
PipeWire configuration and never removes links of other clients (a DAW on
pair 1/2 stays where it is).

Without `[source]` the tool runs in session mode. `status` and `select` on the
command line then need the tray running, because the tray owns the routing
node.

## Usage

```bash
./usb-playback-router               # tray icon
./usb-playback-router status        # exit 0 only if exactly one pair is selected
./usb-playback-router select 3/4
./usb-playback-router pairs
./usb-playback-router diag          # for bug reports
./usb-playback-router autostart on|off|status
./usb-playback-router uninstall     # remove the desktop entries
```

The icon shows the selected pair (`3·4`), a red `!` when the source is linked
to no pair or to more than one, and grey when the device or PipeWire is gone.
State is always derived from the actual PipeWire links, never remembered, so
switching with other tools (`pw-link`, a shell script) is reflected within
milliseconds via `pw-dump -m`.

## Tested hardware

| Device | Profile | Channels | Pairs | Session mode | Source mode |
|---|---|---|---|---|---|
| Mackie ProFX16v3 | analog-surround-40 | 4 | 1/2, 3/4 | yes, measured | yes, in daily use |

`usb-playback-router diag` output from other interfaces is welcome.

## Layout

| | |
|---|---|
| `usb_playback_router/graph.py` | pw-dump snapshot: devices, nodes, ports, links, metadata |
| `usb_playback_router/discovery.py` | device choice, stereo pairs by port order, signal ports |
| `usb_playback_router/backend.py` | derived state, switching, diagnostics |
| `usb_playback_router/config.py`, `devices.toml` | user config, device labels and hints |
| `usb_playback_router/session.py`, `state.py` | session mode: `pw-loopback` node, default sink, remembered pair |
| `usb_playback_router/monitor.py` | `pw-dump -m` change trigger |
| `usb_playback_router/tray.py`, `cli.py`, `autostart.py` | UI, command line, desktop entries |
| `tests/` | unit tests against a real `pw-dump` of the reference setup |

```bash
python3 -m unittest discover -s tests
```
