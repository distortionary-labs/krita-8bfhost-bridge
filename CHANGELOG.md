# Changelog

## Unreleased

Initial release.

- Runs Photoshop-compatible filter plug-ins (`.8bf`) on Krita paint layers through
  8bf-host, a separate program the user installs. On Linux, Windows filters run under Wine
  through 8bf-host's own configuration.
- A **Photoshop Filters (8bf)** menu grouped by filter category, with filters 8bf-host
  cannot run greyed out and the reason in the tooltip.
- 8-bit and 16-bit RGB and 8-bit grayscale layers with alpha, selections with
  auto-masking, and an 8-bit fallback for 16-bit layers with 8-bit-only filters.
- Results go into a new layer by default, or optionally overwrite the active one.
- Repeat Last Filter, which reruns the last filter with its 8bf-host preset and no dialog.
- A settings dialog for the 8bf-host location, with a Check Setup button that runs
  `8bf-host doctor`, plus filter folders, the filter list and About boxes.
