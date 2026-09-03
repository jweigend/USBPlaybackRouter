# USB Playback Router for Linux

## Concept and Technical Design

**Status:** Concept / feasibility draft\
**Target platform:** Linux desktop with PipeWire / WirePlumber\
**Primary use case:** Analog and hybrid USB mixers with more than one
USB playback pair\
**Initial reference device:** Mackie ProFXv3 series

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

No permanent ALSA loopback device should be required.

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

## 5. Important technical distinction

There are two different cases that look identical to the user.

### Case A --- Linux exposes separate stereo playback endpoints

Example:

``` text
USB Audio 1/2
USB Audio 3/4
```

This is the ideal case.

The application only has to change the default PipeWire sink.

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

No virtual device and no loopback are necessary.

### Case B --- Linux exposes one multichannel playback device

Example:

``` text
USB Audio
FL FR AUX0 AUX1
```

or one 4/8/10/32-channel ALSA/PipeWire node.

In this case setting the device as the default sink is not enough. A
normal stereo application sends left/right to the first stereo
positions.

The router therefore needs to map:

``` text
Desktop Left  → hardware channel 3
Desktop Right → hardware channel 4
```

This can still be done **without snd-aloop and without installing a
permanent loopback device**.

The clean PipeWire solution is to create a small runtime routing/remap
node representing the selected stereo pair.

Conceptually:

``` text
Firefox / Spotify / VLC
          │
          ▼
  "USB Playback 3/4"
    PipeWire node
          │
      L ──┼──→ HW channel 3
      R ──┼──→ HW channel 4
          │
          ▼
      USB Mixer
```

This node is a PipeWire software object, not an ALSA loopback sound
card. It can be created when the application starts and removed when it
exits.

From the user's perspective there is still no loopback installation or
configuration.

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
│ route creation              │
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
-   number of playback channels
-   PipeWire nodes
-   available profiles
-   available routes
-   channel positions
-   current default sink

Possible command-line prototypes:

``` bash
wpctl status
wpctl inspect <id>
pw-dump
pw-cli ls Node
```

For development, `pw-dump` is particularly useful because it exposes the
PipeWire object graph as structured JSON.

The production implementation should preferably use a PipeWire
API/binding rather than parse human-readable `wpctl status` output.

------------------------------------------------------------------------

## 8. Stereo-pair discovery

For a device with `N` usable playback channels, the basic UI can offer
consecutive pairs:

``` text
1/2
3/4
5/6
7/8
...
```

However, channel count alone must **not** be assumed to describe the
complete hardware topology.

PipeWire/ALSA may expose:

-   channel maps
-   separate PCM devices
-   profiles
-   subdevices
-   AUX channel positions
-   manufacturer-specific layouts

Therefore discovery should happen in this order:

1.  Look for independently exposed stereo sinks/routes.
2.  Inspect PipeWire channel positions and ALSA capabilities.
3.  Build valid stereo pairs from the exposed hardware channels.
4.  Use a device-specific quirk database only where generic discovery is
    insufficient.

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
      product_family: ProFXv3

    labels:
      "1/2": "USB 1/2 — Monitor / Blend"
      "3/4": "USB 3/4 — Mixer stereo channel"
```

The important distinction is:

**The database provides descriptions, not the fundamental routing
mechanism.**

Unknown devices should continue to work generically.

------------------------------------------------------------------------

## 10. Switching algorithm

When the user selects a stereo pair:

### If a native stereo sink exists

``` text
find sink for pair
→ set it as PipeWire default
→ optionally move existing playback streams
```

### If only a multichannel sink exists

``` text
find hardware sink
→ create/reconfigure PipeWire stereo mapping node
→ map FL/FR to selected hardware channels
→ make mapping node the default sink
→ move existing desktop streams if desired
```

Changing from 1/2 to 3/4 should reuse or replace the mapping rather than
accumulate nodes.

------------------------------------------------------------------------

## 11. No permanent loopback requirement

A design goal should be:

> **No `snd-aloop`, no manually installed virtual sound card and no
> persistent user configuration required.**

PipeWire may internally use a software routing/remapping node when the
hardware exposes only a multichannel sink.

That is fundamentally different from asking the user to configure a
loopback audio device.

The lifecycle should be controlled completely by the application:

``` text
Application starts
      ↓
discover hardware
      ↓
create mapping if required
      ↓
select pair
      ↓
normal desktop playback

Application exits
      ↓
remove temporary mapping
```

A later option could allow the selected routing to persist across
logins.

------------------------------------------------------------------------

## 12. WirePlumber integration

WirePlumber should be used where session-policy integration is needed.

Responsibilities may include:

-   remembering the selected device
-   remembering the selected stereo pair
-   reacting to USB disconnect/reconnect
-   restoring routing after suspend
-   selecting the appropriate default sink
-   handling device IDs that change between sessions

Persistent identification should therefore use stable properties such as
USB/ALSA device properties rather than transient PipeWire numeric IDs.

------------------------------------------------------------------------

## 13. User interface

The UI should remain deliberately small.

### Tray icon

Left click:

``` text
Mackie ProFX16v3

● USB 1/2
○ USB 3/4
```

Selecting a pair switches immediately.

### Context menu

Possible additional functions:

``` text
Device
  Mackie ProFX16v3

Playback pair
  USB 1/2
  USB 3/4

☑ Move currently playing applications
☑ Restore selection when mixer reconnects

Open device information
About
Quit
```

No routing graph should be necessary.

------------------------------------------------------------------------

## 14. Device information view

A small diagnostic window would be valuable both for users and for
development.

Example:

``` text
Device
Mackie ProFX16v3

Backend
PipeWire → ALSA → USB Audio Class

Playback channels
4

Detected pairs
1/2
3/4

Current desktop pair
3/4

ALSA card
ProFX

PipeWire hardware node
alsa_output.usb-...

Mapping
FL → channel 3
FR → channel 4
```

This also makes bug reports much easier.

A **Copy diagnostic information** button would allow users to attach the
topology to GitHub issues.

------------------------------------------------------------------------

## 15. First implementation milestone

The first public version should support:

-   PipeWire
-   WirePlumber
-   one selected USB audio device
-   devices with 2 or more playback channels
-   discovery of available playback topology
-   selection of consecutive stereo pairs
-   switching default desktop playback
-   restoration after reconnect
-   tray UI
-   diagnostics
-   no DAW
-   no JACK configuration
-   no `snd-aloop`

The Mackie ProFX should be the initial reference/test device.

------------------------------------------------------------------------

## 16. Second milestone

After the generic implementation works:

-   collect diagnostic dumps from users
-   test PreSonus, Allen & Heath, Zoom, Soundcraft and Tascam devices
-   build a small device-description/quirk database
-   add friendly hardware labels
-   package as Flatpak/AppImage/deb if appropriate
-   document tested hardware in the README

Example compatibility table:

  Device                       Channels detected   Pair switching      Tested
  -------------------------- ------------------- ---------------- -----------
  Mackie ProFX16v3                             4         1/2, 3/4         Yes
  Mackie ProFX22v3                             4         1/2, 3/4   Community
  PreSonus AR12c                             TBD              TBD      Needed
  Allen & Heath ZEDi                         TBD              TBD      Needed
  Soundcraft Signature MTK                   TBD              TBD      Needed

------------------------------------------------------------------------

## 17. Suggested implementation strategy

For a first prototype, reuse the existing working Mackie tray
application and separate it into three layers:

``` text
UI
│
├── Device discovery
│
└── Routing backend
```

Suggested internal API:

``` python
class AudioDevice:
    id: str
    name: str
    playback_channels: int
    stereo_pairs: list

class RoutingBackend:
    def devices(self): ...
    def current_pair(self, device): ...
    def select_pair(self, device, left, right): ...
    def restore(self): ...
```

The tray code should know nothing about Mackie, ALSA channel numbers or
PipeWire commands.

That makes alternative backends and manufacturer quirks possible later.

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
