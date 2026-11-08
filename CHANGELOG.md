# Changelog

## 1.2.1
- Validate FFmpeg by running it before scanning; missing/broken paths trigger setup instead of passing preflight.
- Validate downloaded FFmpeg before saving the installation.
- Search seven HUD text sizes (75%–150%) automatically instead of two.
- Check every rendered highlight segment for incomplete output and show the number of markers/clips being exported.
- Regression checks retained all seven confirmations in the existing sample and all three distinct segments in a generated export. The reported 3-of-11 misses and first-kill-only export could not be reproduced without the affected recording.

## 1.2.0
- Export all reviewed kill markers as one edited MP4 with audio.
- Editable lead-in, tail and consecutive-kill linking interval. Defaults: 5 / 5 / 60 seconds.
- Nearby kills stay in continuous segments; overlapping windows are merged.
- H.264 CRF 18 video and AAC 192 kbps audio; precise cuts require re-encoding.
- Export progress, cancellation, and existing-file protection.
- Uses the actual Windows Desktop as the initial export location, including redirected Desktops. Cancelling export no longer creates a Finished Videos folder.
- Original recordings stay unchanged. Full-length chapter-marker export remains available.

## 1.0.0
Initial public Windows release.
