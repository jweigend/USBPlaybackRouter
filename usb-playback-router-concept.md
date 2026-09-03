# USB Playback Router for Linux

## Concept and Technical Design

**Status:** Concept / feasibility draft\
**Target platform:** Linux desktop with PipeWire / WirePlumber\
**Primary use case:** Analog and hybrid USB mixers with more than one
USB playback pair\
**Initial reference device:** Mackie ProFXv3 series\
**Origin:** Generalisation of a working single-device tray tool
(`profx16v3-tray`) and its PipeWire configuration (`50-rec-bus.conf`)

------------------------------------------------------------------------

## 1. Problem

Many USB mixers expose more than one playback path from the computer.

A Mackie ProFXv3, for example, exposes two stereo USB return pairs:

-   **USB 1/2** --- useful for monitoring / recording workflows
-   **USB 3/4** --- returned to a stereo mixer channel and therefore
    often the desired path for normal desktop playback

Under Linux this hardware capability is not obvious to the user. Desktop
applications normally play to the system's default audio output, and the
first stereo pair is commonly selected by default.

The result is confusing:

> The mixer is connected and Linux produces audio, but the audio arrives
> at the wrong place in the mixer.

Users can solve this with PipeWire tools, ALSA configuration, patch
bays, scripts, or a DAW, but all of these require knowledge that should
not be necessary for normal playback.

The application proposed here makes the hardware concept visible and
provides a simple switch for it.

------------------------------------------------------------------------

## 2. Goal

Provide a small Linux tray application that answers one question:

> **Which stereo pair of this USB audio device should normal Linux
> desktop audio use?**

Example:

``` text
USB Playback Router
────────────────────────────

Mackie ProFX16v3

● USB 1/2
○ USB 3/4

────────────────────────────
✓ Use for desktop audio
```

Switching to USB 3/4 should immediately move normal playback from
applications such as Firefox, Spotify, VLC or a media player to channels
3/4 of the mixer.

No DAW should be required.

No JACK patch bay should be required.

No manually configured ALSA loopback device should be required.

------------------------------------------------------------------------

## 3. Non-goals

The first version should deliberately **not** become a general audio
workstation.

It should not try to replace:

-   qpwgraph
-   Helvum
-   JACK
-   DAW routing
-   mixer control software
-   PipeWire session managers

The value of the application is its simplicity.

**One device. One playback destination. One stereo pair.**

------------------------------------------------------------------------

## 4. Supported device classes

The program should not initially contain mixer-specific routing logic.

Instead it should inspect the USB audio device and determine what Linux
exposes.

Potentially useful device classes include:

-   Mackie ProFXv3 / ProFXv3+
-   PreSonus StudioLive ARc
-   Allen & Heath ZEDi
-   Zoom LiveTrak
-   Soundcraft Signature MTK
-   Tascam Model series
-   multichannel USB audio interfaces from other manufacturers

A simple 2-channel USB mixer would still be detected, but would offer
only:

``` text
USB 1/2
```

and therefore require no routing selection.

------------------------------------------------------------------------

## 5. What PipeWire actually exposes

There are two different cases that look identical to the user. The
order below reflects how common they are for USB Audio Class devices:
**one multichannel node is the normal case**, separate stereo sinks are
the exception.

### Case A --- one multichannel playback node (normal case)

Example, the reference device on the development machine:

``` text
node.name        alsa_output.usb-LOUD_Technologies_Inc._ProFx-00.analog-surround-40
audio.channels   4
audio.position   FL,FR,RL,RR
profile          analog-surround-40
```

An 8-channel interface typically appears as one node with either
surround positions (`FL FR RL RR FC LFE SL SR`, profile
`analog-surround-71`) or, in the `pro-audio` profile, as
`AUX0 … AUX7`.

Setting this node as the default sink is not enough. A normal stereo
application sends left/right to the first two positions. The router
therefore has to map:

``` text
Desktop Left  → hardware channel 3
Desktop Right → hardware channel 4
```

This is done with a small PipeWire **mapping node** representing the
selected stereo pair. It is a stereo sink that desktop applications see
as their output and whose two channels are linked to the two selected
hardware ports:

``` text
Firefox / Spotify / VLC
          │
          ▼
  "USB Playback 3/4"      stereo Audio/Sink (PipeWire loopback)
          │
      L ──┼──→ playback_RL   (hardware channel 3)
      R ──┼──→ playback_RR   (hardware channel 4)
          │
          ▼
      USB Mixer
```

Technically this is a single `libpipewire-module-loopback` whose capture
side is itself declared as `media.class = Audio/Sink`. No separate
null sink is needed. This is exactly the structure of the existing
`rec-bus` + `rec-bus-abhoere-out` configuration that the Mackie tool
switches today, reduced to one module.

The mapping node is a PipeWire software object, not an ALSA loopback
sound card (`snd-aloop`). From the user's perspective there is no
loopback installation or configuration.

### Case B --- separate stereo playback endpoints (shortcut)

Example:

``` text
USB Audio 1/2
USB Audio 3/4
```

This occurs when an ALSA UCM configuration or a driver splits the device
into several PCMs, or when a device exposes several stereo routes in one
profile. In this case the application only has to change the default
PipeWire sink:

``` text
Desktop Applications
        │
        ▼
     PipeWire
        │
        ├──── USB 1/2
        │
        └──── USB 3/4  ← selected
```

No mapping node is necessary. The application should treat this as an
optimisation, not as the design centre.

### Profiles

The channel layout depends on the active card profile. The ProFx offers
`analog-surround-40`, `pro-audio` and several input/output combinations.
The router should work with whatever profile is active and **must not
switch profiles on its own**: a profile change also reconfigures the
inputs and can break recording setups.

------------------------------------------------------------------------

## 6. Proposed architecture

``` text
┌─────────────────────────────┐
│        Tray Application     │
│                             │
│ Device: Mackie ProFX16v3    │
│                             │
│ ○ USB 1/2                   │
│ ● USB 3/4                   │
└──────────────┬──────────────┘
               │
               │ control
               ▼
┌─────────────────────────────┐
│ PipeWire / WirePlumber      │
│                             │
│ device discovery            │
│ channel discovery           │
│ mapping node + links        │
│ default sink selection      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ ALSA USB Audio Class device │
│                             │
│ Playback 1                  │
│ Playback 2                  │
│ Playback 3                  │
│ Playback 4                  │
└─────────────────────────────┘
```

------------------------------------------------------------------------

## 7. Device discovery

The application should first discover PipeWire devices rather than
identify mixers by USB product name.

Useful information includes:

-   device name
-   ALSA card
-   USB vendor/product information
-   active profile and available profiles
-   number of playback channels and their positions
-   the playback **ports** of the hardware node, in order
-   available routes
-   current default sink
-   existing links from any mapping node to the hardware node

Possible command-line prototypes:

``` bash
wpctl status
wpctl inspect <id>
pw-dump
pw-cli ls Node
```

For development, `pw-dump` is particularly useful because it exposes the
PipeWire object graph as structured JSON, including nodes, ports, links
and the negotiated stream format.

The production implementation should use an API rather than parse
human-readable `wpctl status` output. See section 17.

------------------------------------------------------------------------

## 8. Stereo-pair discovery

For a device with `N` usable playback channels, the basic UI offers
consecutive pairs:

``` text
1/2
3/4
5/6
7/8
...
```

### Pairs are built from port order, not from position names

Channel position names are profile-dependent and semantically misleading
for a mixer: in a 7.1 profile pair 5/6 would be `FC`/`LFE`, in the
pro-audio profile it is `AUX4`/`AUX5`. What the mixer actually has are
USB channels 1 … N in hardware order.

The application should therefore enumerate the playback ports of the
hardware node in their native order and pair them by index:

``` text
port index   port name       USB channel   pair
0            playback_FL     1             1/2
1            playback_FR     2             1/2
2            playback_RL     3             3/4
3            playback_RR     4             3/4
```

Position names are shown only as secondary information in the
diagnostics view.

### Discovery order

1.  Look for independently exposed stereo sinks or routes for the same
    card (Case B). If present, use them directly.
2.  Otherwise take the hardware node of the active profile and its
    playback ports (Case A).
3.  Build consecutive pairs from the port list. An odd trailing channel
    is ignored.
4.  Use a device-specific quirk database only where generic discovery is
    insufficient (section 9).

### Known adapter quirk

A PipeWire stream declared with two channels (for example
`audio.position = [ RL RR ]`) targeting a 4-channel sink still gets
**four** output ports from the adapter. Only the two ports matching the
negotiated format carry signal, the others are silent. WirePlumber may
additionally link the silent ports after a restart.

The implementation must read the negotiated format of the mapping node
to know which ports carry signal, and must remove all links from the
mapping node to the hardware node before creating the intended two. The
existing Mackie tool already does both; the behaviour has to be carried
over, not rediscovered.

------------------------------------------------------------------------

## 9. Optional device knowledge database

Generic operation should be the default.

A small database can later improve the user experience without making
the application dependent on specific manufacturers.

Example:

``` yaml
devices:
  - match:
      vendor: Mackie
      product_family: ProFxv3

    labels:
      "1/2": "USB 1/2 — Control Room / monitor"
      "3/4": "USB 3/4 — stereo channel strip → Main Mix"

    hints:
      "1/2": "Mute the USB return channel strip on the mixer."
      "3/4": "The channel fader now controls desktop volume."
```

The important distinction is:

**The database provides descriptions and hints, not the fundamental
routing mechanism.**

Unknown devices should continue to work generically with labels
`USB 1/2`, `USB 3/4`, ….

------------------------------------------------------------------------

## 10. State and switching

### State is derived from the graph, never stored

The application must not remember "the user selected 3/4" and assume
that this is true. It reads the PipeWire graph and derives the state from
the actual links between the mapping node (or, in Case B, the default
sink) and the hardware node. This is the most important property of the
existing Mackie tool and the reason it stays correct after manual
`pw-link` work, PipeWire restarts and reconnects.

Derived states:

``` text
1/2, 3/4, …   exactly one pair is linked
ambiguous     more than one pair is linked
none          the mapping node exists but has no signal-carrying link
no mapping    the device is present but the mapping node is missing
offline       device not connected, or PipeWire not running
```

Every state has a distinct tray icon. `ambiguous` and `none` show a
warning icon and a headline that tells the user to pick a pair; the pair
selection stays enabled. `offline` disables the selection.

The graph is re-read on every PipeWire change event (preferred) or by
polling every few seconds (prototype).

### Switching to a pair

If separate stereo sinks exist (Case B):

``` text
find the sink for the pair
→ set it as PipeWire default sink
```

Otherwise (Case A):

``` text
ensure the mapping node exists (create it once, reuse afterwards)
→ remove every link from the mapping node to the hardware node
→ link mapping L → hardware port 2·k, mapping R → hardware port 2·k+1
→ ensure the mapping node is the default sink
→ re-read the graph and confirm the derived state matches
```

Changing from 1/2 to 3/4 relinks the one existing mapping node. It never
creates a second node.

### Streams follow the default sink

With WirePlumber, application streams follow the default sink
automatically unless an application has pinned itself to a specific
target. A separate "move currently playing applications" step is
therefore not needed in the normal case; the application may offer it as
a repair action for pinned streams.

### Notification

After a switch, a desktop notification shows the new pair and, if the
device database has one, the hint for the mixer (for example "mute the
USB return channel strip").

------------------------------------------------------------------------

## 11. Lifecycle and persistence

A design goal is:

> **No `snd-aloop`, no manually installed virtual sound card and no
> hand-written PipeWire configuration required.**

The mapping node is created by the application. There are two lifetimes,
and the user chooses between them.

### Session mode (default for a first try)

The application owns the mapping node. It is created when the
application starts, for example by running `pw-loopback` as a child
process or by loading the loopback module in-process, and disappears
when the application exits.

``` text
Application starts
      ↓
discover hardware
      ↓
create mapping node if required
      ↓
link selected pair, set default sink
      ↓
normal desktop playback

Application exits
      ↓
mapping node disappears, default sink falls back
```

The price: when the application is not running, desktop audio falls back
to another sink and the mixer routing is gone.

### Persistent mode (recommended once the routing works)

The application writes a small drop-in file to
`~/.config/pipewire/pipewire.conf.d/` that declares the same mapping
node with the last selected pair as `audio.position`. PipeWire then
creates the node at every login, whether the tray tool runs or not, and
the tray tool becomes what the Mackie tool is today: only the switch and
the indicator.

The drop-in is written and removed by the application ("Enable at
login" / "Disable at login"). The user never edits it. This is the same
mechanism as the existing `50-rec-bus.conf`, generated instead of
hand-written.

Because the mapping node has a stable `node.name`, WirePlumber remembers
it as the default sink across restarts on its own. No additional
persistence code is required for that.

### Reconnect and suspend

The application watches the graph. When the hardware node disappears
(USB unplugged, suspend) the state becomes `offline`. When it reappears,
the application re-links the last derived pair. In persistent mode
PipeWire and WirePlumber restore the links from `audio.position` anyway;
the application only has to verify and, if necessary, repair.

------------------------------------------------------------------------

## 12. WirePlumber

WirePlumber is used, not extended. No custom session policy or Lua
script is planned.

What WirePlumber already provides for free:

-   remembering the default sink by stable `node.name`
-   moving application streams to the default sink
-   linking a stream to a sink by channel position
-   re-linking after device reconnect

What the application handles itself:

-   which hardware ports the mapping node is linked to
-   verification and repair after reconnect
-   removal of unwanted links created for the silent adapter ports

Persistent identification of the device uses stable properties such as
`device.name`, `device.bus-path` or the USB vendor/product IDs, never
transient PipeWire numeric IDs.

------------------------------------------------------------------------

## 13. User interface

The UI should remain deliberately small.

### Tray icon

The icon shows the derived state: the selected pair, a warning for
`ambiguous` / `none`, or a greyed-out icon for `offline`. The tooltip
shows the headline text.

Left or right click opens the menu:

``` text
Desktop audio → USB 3/4 — stereo channel strip → Main Mix
────────────────────────────
● USB 1/2 — Control Room / monitor
○ USB 3/4 — stereo channel strip → Main Mix
────────────────────────────
☐ Enable at login
Refresh now
Device information…
About
Quit
```

Selecting a pair switches immediately.

The tray backend is `XApp.StatusIcon` where available (Cinnamon) and
`AyatanaAppIndicator3` as fallback, as in the existing tool.

### Command line

The same executable works without a tray, so scripts, keyboard
shortcuts and other tools can use it:

``` bash
usb-playback-router               # start the tray icon
usb-playback-router status        # print the derived state, exit 0 only if one pair is selected
usb-playback-router select 3/4    # switch
usb-playback-router pairs         # list detected pairs
usb-playback-router diag          # print diagnostic information (section 14)
```

Only one tray instance runs at a time (lock file in `$XDG_RUNTIME_DIR`),
so autostart and a manual start do not duplicate the icon.

No routing graph should be necessary.

------------------------------------------------------------------------

## 14. Device information view

A small diagnostic window would be valuable both for users and for
development.

Example:

``` text
Device
Mackie ProFx (LOUD Technologies Inc.)

Backend
PipeWire 1.0.5 → ALSA → USB Audio Class

Profile
analog-surround-40  (available: pro-audio, …)

Playback channels
4  (FL FR RL RR)

Detected pairs
1/2  → playback_FL, playback_FR
3/4  → playback_RL, playback_RR

Derived state
3/4

Mapping node
usb-playback-router  (session)   L → playback_RL, R → playback_RR

Default sink
usb-playback-router
```

This also makes bug reports much easier.

A **Copy diagnostic information** button (and `usb-playback-router diag`)
outputs this text plus the relevant `pw-dump` excerpt for the device,
so users can attach the topology to GitHub issues.

------------------------------------------------------------------------

## 15. First implementation milestone

The first public version should support:

-   PipeWire and WirePlumber
-   one selected USB audio device
-   devices with 2 or more playback channels
-   discovery of the active profile and the playback ports
-   consecutive stereo pairs by port index
-   mapping node in session mode
-   state derived from the graph, including the warning states
-   switching default desktop playback
-   verification and repair after reconnect
-   tray UI and command line
-   diagnostics
-   no DAW, no JACK configuration, no `snd-aloop`

The Mackie ProFX should be the initial reference/test device.

------------------------------------------------------------------------

## 16. Second milestone

After the generic implementation works:

-   persistent mode (generated drop-in)
-   collect diagnostic dumps from users
-   test PreSonus, Allen & Heath, Zoom, Soundcraft and Tascam devices
-   build a small device-description/quirk database
-   add friendly hardware labels and mixer hints
-   Case B support (separate stereo sinks) once a device that needs it is
    available
-   package as Flatpak/AppImage/deb if appropriate
-   document tested hardware in the README

Example compatibility table:

  Device                       Profile               Channels   Pairs        Tested
  -------------------------- ------------------- ---------- ---------- -----------
  Mackie ProFX16v3           analog-surround-40           4   1/2, 3/4         Yes
  Mackie ProFX22v3           analog-surround-40           4   1/2, 3/4   Community
  PreSonus AR12c             TBD                        TBD        TBD      Needed
  Allen & Heath ZEDi         TBD                        TBD        TBD      Needed
  Soundcraft Signature MTK   TBD                        TBD        TBD      Needed

The profile column matters because it determines the channel layout and
therefore the behaviour of pair discovery.

------------------------------------------------------------------------

## 17. Suggested implementation strategy

For a first prototype, reuse the existing working Mackie tray
application and separate it into three layers:

``` text
UI  (tray, CLI, notifications)
│
├── Discovery  (device, profile, ports, pairs, derived state)
│
└── Routing backend  (mapping node, links, default sink, drop-in)
```

Suggested internal API:

``` python
class AudioDevice:
    id: str                  # stable: device.name / bus path
    name: str
    profile: str
    playback_ports: list     # hardware port names in order
    stereo_pairs: list       # [(index, left_port, right_port), ...]

class RoutingBackend:
    def devices(self): ...
    def state(self, device): ...            # pair index | 'ambiguous' | 'none' | 'no mapping' | 'offline'
    def select_pair(self, device, index): ...
    def ensure_mapping(self, device): ...
    def persist(self, device, enabled): ... # write / remove the drop-in
```

The tray code should know nothing about Mackie, port names or PipeWire
commands.

### Existing chains as source

The mapping node does not have to be created by the application. If a
user already has a virtual sink feeding the hardware node (as in the
current Rec-Bus setup, where other tools such as a DAW or a delay tool
depend on that sink being the default), the backend can be pointed at
that node as the **source** and only relinks its outputs to the selected
hardware pair. This is the mode the existing Mackie tool implements; the
generic tool must keep it, otherwise it would replace such setups instead
of controlling them.

### PipeWire access

-   **Prototype:** `pw-dump` for reading the graph, `pw-link` for
    creating and deleting links, `wpctl set-default` for the default
    sink, `pw-loopback` as a child process for the mapping node.
    Polling every two seconds is acceptable here.
-   **Production:** the WirePlumber client library via GObject
    introspection (`gi.repository.Wp`). It gives nodes, ports, links,
    the default sink and change events from the same GLib main loop the
    GTK tray already uses, so no polling and no subprocess parsing. There
    is no maintained Python binding for `libpipewire` itself; `Wp` is
    the practical API for a Python/GTK application.

------------------------------------------------------------------------

## 18. Project positioning

The project should not advertise itself as another Linux audio routing
system.

A clearer description is:

> **A tiny Linux tray utility that lets you choose which stereo output
> pair of a multichannel USB audio interface receives normal desktop
> audio.**

Or even shorter:

> **Send Linux desktop audio to USB 1/2, 3/4, 5/6 ... without opening a
> DAW or patch bay.**

That immediately explains the problem being solved.

------------------------------------------------------------------------

## 19. Working project names

Possible neutral names:

-   USB Playback Router
-   USB Pair
-   AudioPair
-   PairRoute
-   USB Audio Switch
-   PipePair

A generic name is preferable if support is intended to extend beyond
Mackie.

------------------------------------------------------------------------

## 20. Core design principle

The project should preserve the simplicity of the original solution:

> **The user should not need to understand PipeWire in order to use the
> routing capabilities of their USB mixer.**

PipeWire is the implementation detail.

The mixer and its USB playback pairs are the user-facing model.

Two rules from the original tool carry over unchanged:

1.  The state shown to the user is always derived from the real graph.
2.  Switching means: remove all links of the source to the hardware,
    then create exactly two.
