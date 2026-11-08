# NOATY Kill Finder

## [⬇ Download for Windows](https://github.com/noaty/Noaty-Wardogs-Kill-Finder/releases/latest/download/Noaty-Kill-Finder-Windows-v1.2.1.zip)

**Download ZIP → Extract all → Open Noaty Kill Finder.exe.**

Find WARDOGS kill confirmations in a recording and turn them into clickable video chapters. Runs on your PC, without AI or uploading footage.

## Download and use

Download the Windows ZIP from this repository's **Releases**, then **extract the entire folder**. Open `Noaty Kill Finder.exe`; keep `_internal` beside it.

1. Drop a finished recording into the app.
2. Click **Scan for kills**. Review the detected timestamps and frame previews.
3. Click **Save video with markers** to create a new MP4.
4. Click **Open marker viewer**, then drop in the marked copy to jump between kills.

**First use:** if FFmpeg is not already installed, click **Yes** on the one-time setup prompt. The app downloads and verifies its scanner component from PyPI, then remembers it. No Python, terminal commands, or manual file selection required. Internet is needed for this initial download only; your videos stay local. You can also provide your own `ffmpeg.exe` beside the app.

The source video is never overwritten. For marker export, video and audio are copied without re-encoding. The marked copy needs approximately the same disk space as the source.

## Features

- Automatic 75%, 85%, 90%, 100%, 110%, 125% and 150% notification-text matching, including size changes within a video.
- Counts separate stacked confirmation lines, including tested double kills.
- Timestamp list, frame preview, remove/restore, and optional manual corrections.
- New Clip reset, cancellation, full-decoded-duration reporting, and incomplete-scan detection.
- Embedded MP4 chapters and optional CSV, TXT and JSON exports.
- Existing chapters preserved; a recording-start chapter is added when needed.
- Included local HTML chapter viewer. No server or account needed.

## What it detects

This is template matching against the visible **KILL CONFIRMED** notification, not a scoreboard reader or an AI model. Default scanning samples 10 frames per second. Times follow the first confidently detected notification, not the exact shot.

Hidden, faded, obstructed, heavily compressed, differently styled, or continuously overlapping notifications can be missed. If an old popup is replaced by a new one without changing the visible line count, they can merge. Review results before editing. Match percentages are template similarity, **not accuracy probabilities**.

Calibration checks on private recordings found seven notifications in a 48.4-second sample and three in a 10:50.9 recording, including two near 9:44.5 and 9:46.2. Those recordings are not distributed. These are regression checks, not a guarantee for every video.

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
.venv\Scripts\python -m unittest test_engine -v
.venv\Scripts\python build_windows.py
```

Output: `dist/Noaty-Kill-Finder-Windows-v1.2.1.zip`. Building is supported on Windows. The included tests cover synthetic detection and video export. Public builds are unsigned.

## Privacy

No telemetry, accounts or video uploads. Detection and export run locally. The downloaded scanner component is stored in `%APPDATA%/Noaty Kill Finder/runtime/`. The one-time download contacts PyPI; it does not transmit videos. Exported sidecars contain the input filename/path and scan metadata; review them before sharing. The included viewer processes files locally.

## Support

When reporting a problem, include the app version, resolution, HUD scale, approximate missed timestamp, and a short sample if you choose to share one. Avoid posting private recordings or personal paths in public issues.

## Rights

Copyright 2026 NOATY. **All rights reserved**; public source visibility is not an open-source reuse license. See [COPYRIGHT.txt](COPYRIGHT.txt) and [THIRD_PARTY.md](THIRD_PARTY.md). Unofficial WARDOGS community project; not affiliated with the game's developers.

## Automatic highlight video export (1.2.1)

Scan and review your markers, then click **EXPORT KILL HIGHLIGHTS**. Change the timing fields if desired: **Before 5 seconds**, **After 5 seconds**, and **Keep together 60 seconds** by default. Kills within the linking interval of the previous kill stay in a continuous segment; separate segments are joined into one MP4. Overlapping windows are merged to avoid duplicated footage. Original recordings remain unchanged.

The save window starts on your Windows Desktop. Choose any output folder; cancelling does not create an export folder. Rendering runs locally, with progress and cancellation. Highlight export re-encodes at H.264 CRF 18 / AAC 192 kbps and is not lossless. **Save video with markers** instead preserves the full recording without re-encoding.

