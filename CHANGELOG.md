# Changelog

## 1.3.1
- Include the certificate-policy resource required by the build runtime, fixing first-use FFmpeg setup failing with FileNotFoundError. HTTPS verification remains enabled.
- Test first-use setup and audio scanning from a freshly extracted Windows package.

## 1.3.0
- Save detection preferences between launches; Reset defaults restores recommended values before saving.
- Denser fallback visual checks around audio candidates and finer glyph-size matching, without reducing the match threshold.
- Animated ON/OFF export switches on every result; a bulk Remove all OFF control.
- Refreshed desktop UI with larger frame preview, visible detection mode and export controls.
- Default audio-first mode visually checks only nearby candidate frames. Unverified candidates are amber and excluded until manually kept; click FLAG/KEEP or use Remove all flagged. All exports honor those choices. Audio-only and visual-only remain available.
- Detect kills by the kill-confirm chime in the game audio. The chime's narrow partials near 12.9 kHz and 16.8 kHz are measured against their neighbouring frequencies, to help reject broadband noise and the result does not depend on resolution, HUD scale or window layout.
- Whisky reports his 53-minute recording scans in about 24 seconds instead of over an hour; speed varies by hardware and recording. All eleven detections in that recording line up with a visible KILL CONFIRMED notification; one of them is a double kill reported as a single marker.
- New Detection settings: detection method, sound sensitivity in dB, and audio track. Auto scans the first track and checks the others only when nothing is found; All tracks scans every track in one pass.
- The Match column shows chime prominence in dB for sound detections; exported JSON records the method, tracks scanned and hits per track.
- Notification-text matching remains available as the second method for recordings without game audio. Its behaviour is unchanged.
- Add a three-lower-partial alternative for edited audio whose encoder removes the upper chime frequency; validated 70 markers against visible confirmations in seven finished edits.
- Credit: audio scanner and integration contributed by whiskysix (Whisky).
- Avoid counting a continuous tone twice across processing chunks; add guidance when no audio matches are found.
- No new dependencies; the spectral analysis uses NumPy only.

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
