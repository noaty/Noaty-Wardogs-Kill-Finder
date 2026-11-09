# NOATY Kill Finder

## [⬇ Download for Windows](https://github.com/noaty/Noaty-Wardogs-Kill-Finder/releases/latest/download/Noaty-Kill-Finder-Windows-v1.3.1.zip)

**Download ZIP → Extract all → Open Noaty Kill Finder.exe.**

Find WARDOGS kill confirmations in a recording and turn them into clickable video chapters. Runs on your PC, without AI or uploading footage. The default mode finds audio candidates, then checks only nearby video frames for confirmation text. Speed varies by PC, codec and audio-track selection.

## Download and use

Download the Windows ZIP from this repository's **Releases**, then **extract the entire folder**. Open `Noaty Kill Finder.exe`; keep `_internal` beside it.

1. Drop a finished recording into the app.
2. Click **Scan for kills**. Review the detected timestamps and frame previews.
3. Click **Save video with markers** to create a new MP4.
4. Click **Open marker viewer**, then drop in the marked copy to jump between kills.

**First use:** if FFmpeg is not already installed, click **Yes** on the one-time setup prompt. The app downloads and verifies its scanner component from PyPI, then remembers it. No Python, terminal commands, or manual file selection required. Internet is needed for this initial download only; your videos stay local. You can also provide your own `ffmpeg.exe` beside the app.

The source video is never overwritten. For marker export, video and audio are copied without re-encoding. The marked copy needs approximately the same disk space as the source.

## Features

- Kill-confirm sound detection: independent of resolution, HUD scale and window layout, with speed dependent on your PC and recording.
- Automatic audio-track handling for multi-track recordings (Medal, OBS); choose a track or scan all of them in Detection settings.
- Optional notification-text matching (50%–200% HUD sizes with low-resolution alignment variants) for recordings without game audio. It counts separate stacked confirmation lines, including tested double kills.
- Timestamp list, frame preview, remove/restore, and optional manual corrections.
- New Clip reset, cancellation, full-decoded-duration reporting, and incomplete-scan detection.
- Embedded MP4 chapters and optional CSV, TXT and JSON exports.
- Existing chapters preserved; a recording-start chapter is added when needed.
- Included local HTML chapter viewer. No server or account needed.

## What it detects

The audio detector listens for the kill-confirm chime, not a scoreboard reader or an AI model. The original detector checks narrow tonal partials near 12.9 kHz and 16.8 kHz. For encoded audio that loses the upper partial, an alternative requires all three lower partials near 11.1, 12.9 and 14.8 kHz together. Gunfire and voices are broadband, so the scanner measures how far those partials rise above the neighbouring frequencies instead of how loud they are; this helps reject broadband sounds, but false matches are still possible. The **Signal** column shows that prominence in dB (default sensitivity 12 dB). Times follow the start of the chime, which may lead it by up to 0.17 seconds, not the exact shot.

Kills less than 0.6 seconds apart (for example one bullet through two players) share one marker. Recordings without game audio, with the game muted, or whose audio encoder removes the required chime frequencies may not produce matches; switch to **Notification text** in Detection settings. **Auto** scans the first audio track, which may be the full mix depending on recording settings, and only checks the remaining tracks when nothing is found there.

The **Notification text** method is template matching against the visible **KILL CONFIRMED** notification, sampling 10 frames per second. It is far slower (roughly real time or longer) and depends on the HUD being visible and legible. Hidden, faded, obstructed, heavily compressed, differently styled, or continuously overlapping notifications can be missed. If an old popup is replaced by a new one without changing the visible line count, they can merge. Match percentages are template similarity, **not accuracy probabilities**. Review results before editing with either method.

Calibration checks on private recordings: Whisky reports that the sound method found eleven confirmations in his 53:28 Medal recording in 24 seconds. Every one lines up with a visible notification (one is a double kill reported as a single marker), the same eleven appear on both the mix and the game-audio track, and none appear on the microphone tracks. Notification-text checks found seven notifications in a 48.4-second sample and three in a 10:50.9 recording, including two near 9:44.5 and 9:46.2. Those recordings are not distributed. These are regression checks, not a guarantee for every video.

MP4, MOV and MKV can be scanned when FFmpeg supports their codecs. Some MKV audio/subtitle streams cannot be copied into MP4; export then fails safely instead of silently re-encoding. Browser playback in the viewer also depends on codec support. Chapter extraction can still work without playback.

One recording is processed per window. A batch queue is not included. Choose full-length marker export or automatic edited highlight export.

## Run from source

Windows 10/11, Python **3.12** (64-bit):

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

The `imageio-ffmpeg` dependency can provide FFmpeg for source installations. The standalone public ZIP omits its executable.

## Test and build

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m unittest test_audio test_engine -v
.venv\Scripts\python build_windows.py
```

Output: `dist/Noaty-Kill-Finder-Windows-v1.3.1.zip`. Building is supported on Windows. The included tests cover synthetic sound and notification detection, multi-track selection, and video export. Public builds are unsigned.

## Privacy

No telemetry, accounts or video uploads. Detection and export run locally. The downloaded scanner component is stored in `%APPDATA%/Noaty Kill Finder/runtime/`. The one-time download contacts PyPI; it does not transmit videos. Exported sidecars contain the input filename/path and scan metadata; review them before sharing. The included viewer processes files locally.

## Support

When reporting a problem, include the app version, detection method, recording software and audio track layout, resolution, HUD scale, approximate missed timestamp, and a short sample if you choose to share one. Avoid posting private recordings or personal paths in public issues.

Local validation of the integrated scanner: seven finished edits (about 20 minutes 51 seconds total) produced 70 audio markers in about 10 seconds; inspected frames at all 70 timestamps showed kill confirmations. This verifies detected moments, not that every kill was counted. Closely spaced kills can share a marker.

## Credits

Audio detection and the integration patch contributed by **whiskysix (Whisky)**.

## Rights

Copyright 2026 NOATY. **All rights reserved**; public source visibility is not an open-source reuse license. See [COPYRIGHT.txt](COPYRIGHT.txt) and [THIRD_PARTY.md](THIRD_PARTY.md). Unofficial WARDOGS community project; not affiliated with the game's developers.

## Automatic highlight video export (1.3.1)

Scan and review your markers, then click **EXPORT KILL HIGHLIGHTS**. Change the timing fields if desired: **Before 5 seconds**, **After 5 seconds**, and **Keep together 60 seconds** by default. Kills within the linking interval of the previous kill stay in a continuous segment; separate segments are joined into one MP4. Overlapping windows are merged to avoid duplicated footage. Original recordings remain unchanged.

The save window starts on your Windows Desktop. Choose any output folder; cancelling does not create an export folder. Rendering runs locally, with progress and cancellation. Highlight export re-encodes at H.264 CRF 18 / AAC 192 kbps and is not lossless. **Save video with markers** instead preserves the full recording without re-encoding.


### Audio + visual review (default)
Audio finds candidates first; a short nearby window at 10 frames per second when the quick check is inconclusive are checked for notification text, with two matches required. Verified candidates are included. Amber candidates are unverified and excluded by default, not automatically declared false. Use the animated ON/OFF switch in the Export column (or select a row and press Space) to toggle inclusion. Remove all OFF removes excluded rows; Restore results restores the original scan decisions. Timestamp, marked-video and highlight exports all use only included markers. A flagged moment can still appear within the surrounding footage of another included marker, especially with long Keep together settings. Audio-only and visual-only modes remain available.

On a private 44-minute recording, audio took about 21 seconds and the strengthened candidate verification added about 11 seconds; a known inventory false positive was flagged. After finer text-size matching, verification accepted all 70 previously reviewed highlight candidates. The reported sniper confirmation at 21:30.310 was verified while the inventory false positive stayed excluded. These are sample measurements, not guarantees of speed or complete detection.

Detection settings: SAVE applies and remembers your preferences between launches. Reset defaults restores recommended values in the dialog; click SAVE to keep them. Closing the dialog without saving discards edits.
