# Changelog

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
