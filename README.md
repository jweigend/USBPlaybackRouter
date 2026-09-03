# USB Playback Router

**Send Linux desktop audio to USB 1/2, 3/4, 5/6 … of a multichannel USB
audio interface without opening a DAW or patch bay.**

Many USB mixers (Mackie ProFXv3, PreSonus ARc, Allen & Heath ZEDi, …) expose
more than one stereo return pair from the computer. Linux shows them as one
"Surround 4.0" device and plays everything to the first pair. This tray icon
shows which pair desktop audio reaches and switches it with one click.

Concept and design: [usb-playback-router-concept.md](usb-playback-router-concept.md).

## Status

Milestone 0. **Source mode** works and is verified on the reference setup
(Mackie ProFX16v3 with a PipeWire loopback feeding the mixer): the tool
replaces a device-specific predecessor one to one. **Session mode** (the tool
creates the routing node itself) is the next milestone.

## Requirements

| | |
|---|---|
| backend | `pipewire-bin` (`pw-dump`, `pw-link`, `pw-loopback`, `pw-metadata`) |
| UI | Python ≥ 3.11, `python3-gi`, `gir1.2-gtk-3.0` |
| tray | `gir1.2-xapp-1.0` (Cinnamon) or `gir1.2-ayatanaappindicator3-0.1` |

No pip packages, no library binding to PipeWire or WirePlumber. WirePlumber
only has to be running, any version.

## Configuration

`~/.config/usb-playback-router.conf`:

```ini
[device]
name = alsa_card.usb-LOUD_Technologies_Inc._ProFx-00   ; optional, auto-detected otherwise

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

Without `[source]` the tool reports that session mode is not implemented yet.

## Usage

```bash
./usb-playback-router               # tray icon
./usb-playback-router status        # exit 0 only if exactly one pair is selected
./usb-playback-router select 3/4
./usb-playback-router pairs
./usb-playback-router diag          # for bug reports
./install.sh                        # symlink into ~/.local/bin + autostart entry
./install.sh remove
```

The icon shows the selected pair (`3·4`), a red `!` when the source is linked
to no pair or to more than one, and grey when the device or PipeWire is gone.
State is always derived from the actual PipeWire links, never remembered, so
switching with other tools (`pw-link`, a shell script) is reflected within
milliseconds via `pw-dump -m`.

## Layout

| | |
|---|---|
| `usb_playback_router/graph.py` | pw-dump snapshot: devices, nodes, ports, links, metadata |
| `usb_playback_router/discovery.py` | device choice, stereo pairs by port order, signal ports |
| `usb_playback_router/backend.py` | derived state, switching, diagnostics |
| `usb_playback_router/config.py`, `devices.toml` | user config, device labels and hints |
| `usb_playback_router/monitor.py` | `pw-dump -m` change trigger |
| `usb_playback_router/tray.py`, `cli.py` | UI |
| `tests/` | unit tests against a real `pw-dump` of the reference setup |

```bash
python3 -m unittest discover -s tests
```
