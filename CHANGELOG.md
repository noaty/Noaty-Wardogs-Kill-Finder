# Changelog

## 1.2.3
- Fix corrupted punctuation in the app title, workflow labels, scan speed, previews and progress messages.
- Use plain-text separators so these labels remain readable across Windows locale settings.
- Detection and export behavior are unchanged from 1.2.2.

## 1.2.2
- Resolution-aware text templates retain matching detail at 480p and 720p. Low-resolution alignment checks take more processing time.
- Wider 50%–200% HUD size coverage and a taller search area; narrow frames are padded before the center crop.
- Merge overlapping match boxes across template sizes instead of suppressing only top-left rows.
- Generated-video checks passed at 854x480, 1280x720, 1920x1080, 2560x1440, 3840x2160, 2560x1080, 3440x1440, 5120x1440, 1280x1024, and 1920x1200.
- A seven-second gameplay segment retained its one expected confirmation when resized to 480p, 720p, 1440p and 4K.
- These checks do not guarantee every recording: cropped/letterboxed footage, hidden or heavily compressed text and custom HUD placement may still miss notifications.

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
