# Changelog

## 0.1.1 — 2026-09-03

- Single-file executable: `build.sh` packs the package into
  `usb-playback-router-<version>.pyz` (Python zipapp), attached to every
  GitHub release. Package data is read via `importlib.resources`.
- Logo PNG and tray-menu screenshot for the README and SourceForge.
- Session mode: a remembered pair is verified once after the routing node
  starts, not on every graph change. A duplicated controller in `session.py`
  had reapplied it every two seconds and reverted manual `pw-link` work.
- Auto-detection only picks USB devices. A multichannel non-USB card (HDMI in
  a surround profile) is no longer chosen when the mixer is absent; force it
  with `[device] name` if wanted.

## 0.1.0 — 2026-09-03

First release.

- Session mode: the tool creates a stereo routing sink with `pw-loopback`,
  makes it the default sink and links it to the chosen hardware pair. The
  pair is remembered per device and reapplied after a reconnect; leftover
  nodes from a crashed instance are cleaned up on start.
- Source mode: an existing loopback feeds the mixer and the tool only relinks
  it. Never touches the default sink or other clients' links.
- Tray icon (XApp or AppIndicator) with per-pair icons, warning and offline
  states, device information dialog, "Start at login" toggle.
- Command line: `status`, `select`, `pairs`, `diag`, `autostart`.
- State is always derived from the PipeWire graph; changes are followed via
  `pw-dump -m`. Backend depends on `pipewire-bin` only.
- Device database with labels and hints (Mackie ProFXv3).
- Verified on a Mackie ProFX16v3 (PipeWire 1.0.5, WirePlumber 0.4.17) with a
  measured test signal on all four channels.
