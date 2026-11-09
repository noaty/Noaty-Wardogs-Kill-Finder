"""Offline kill-confirm sound detection. No model or network calls.

The WARDOGS kill confirmation plays a short metallic "ding" with very narrow
tonal partials near 12,926 Hz and 16,828 Hz, plus weaker ones near 11,062 Hz
and 14,783 Hz. Gunfire, footsteps and voices are broadband, so instead of
loudness we measure how far each partial rises above its neighbouring
frequencies (its "prominence"). That survives even when a shot is much louder
than the ding, and it does not depend on the recording resolution or HUD scale.

Audio is streamed out of FFmpeg and analysed a few seconds at a time, so memory
use stays flat however long the recording is. A 53-minute recording scans in
about half a minute in Whisky's reported benchmark; speed varies by machine
and audio-track selection.
"""

import re
import math
import subprocess
import tempfile
import threading
import time

import numpy as np

from engine import FLAGS, Cancelled, ffmpeg, probe, timestamp

SR = 48000
# Chime partials: both primaries OR the first primary plus both secondaries.
PRIMARY = (12926, 16828)
SECONDARY = (11062, 14783)
BAND_HZ = 25  # half-width of the "on tone" band
SIDE_NEAR, SIDE_FAR = 80, 400  # neighbouring band used as the reference level

NPERSEG = 8192  # ~5.9 Hz bins: fine enough to separate the partials from noise
HOP = 480  # 10 ms between analysis windows
CHUNK_SEC = 10  # seconds of audio analysed at a time
DEFAULT_THRESHOLD = 12.0  # dB both primary partials must rise above neighbours
MIN_GAP = 0.6  # seconds; dings closer than this are reported as one event
FULL_CONFIDENCE_DB = 24.0  # strength shown as 100% in the results list
ALL_TRACKS = "all"


def _tukey(n, alpha=0.25):
    """Periodic Tukey window, matching scipy.signal.get_window(('tukey', .25), n)."""
    m = n + 1
    w = np.ones(m)
    width = int(np.floor(alpha * (m - 1) / 2.0))
    k = np.arange(0, width + 1)
    taper = 0.5 * (1 + np.cos(np.pi * (-1 + 2.0 * k / alpha / (m - 1))))
    w[: width + 1] = taper
    w[m - width - 1 :] = taper[::-1]
    return w[:-1].astype(np.float32)


WINDOW = _tukey(NPERSEG)
FREQS = np.fft.rfftfreq(NPERSEG, 1 / SR)


def _bands(f0):
    distance = np.abs(FREQS - f0)
    on = np.flatnonzero(distance <= BAND_HZ)
    side = np.flatnonzero((distance >= SIDE_NEAR) & (distance <= SIDE_FAR))
    return on, side


BANDS = {f: _bands(f) for f in PRIMARY + SECONDARY}
# Only these spectrum columns are ever needed, so the rest is never squared.
NEEDED = np.unique(np.concatenate([np.concatenate(b) for b in BANDS.values()]))
LOOKUP = {
    f: (np.searchsorted(NEEDED, on), np.searchsorted(NEEDED, side))
    for f, (on, side) in BANDS.items()
}


def prominence(power, f0):
    """dB by which the band around f0 rises above its neighbours, per window."""
    on, side = LOOKUP[f0]
    return 10 * np.log10(power[:, on].mean(1) + 1e-14) - 10 * np.log10(
        power[:, side].mean(1) + 1e-14
    )


def score_frames(samples):
    """Per-window detection score and secondary-partial bonus for mono float audio.

    Window ``i`` covers samples ``[i*HOP, i*HOP+NPERSEG)``. Returns two empty
    arrays when fewer than NPERSEG samples are given.
    """
    samples = np.asarray(samples, dtype=np.float32)
    if len(samples) < NPERSEG:
        return np.zeros(0, np.float32), np.zeros(0, np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(samples, NPERSEG)[::HOP]
    spectrum = np.fft.rfft(frames * WINDOW, axis=1)[:, NEEDED]
    power = spectrum.real**2 + spectrum.imag**2
    p = {f: prominence(power, f) for f in PRIMARY + SECONDARY}
    original = np.minimum(p[PRIMARY[0]], p[PRIMARY[1]])
    # Some encoders remove the 16.8 kHz partial. Require ALL THREE lower
    # partials together rather than accepting a lone tone.
    filtered_audio = np.minimum(np.minimum(p[PRIMARY[0]], p[SECONDARY[0]]), p[SECONDARY[1]])
    score = np.maximum(original, filtered_audio)
    bonus = np.maximum(p[SECONDARY[0]], p[SECONDARY[1]])
    return score, bonus


def onsets(score, bonus, threshold, start=0.0, last=None, min_gap=MIN_GAP, continued=False):
    """Turn per-window scores into (onset, end, strength_db, secondary_db, index) hits.

    ``start`` is the file time of window 0 and ``index`` is the window with the
    peak score. ``last`` is the onset of the most recent hit from a previous
    call, so that the minimum gap also applies across chunk boundaries.
    """
    hits = []
    above = score > threshold
    i = 0
    n = len(score)
    if continued:
        while i < n and above[i]:
            i += 1
    while i < n:
        if not above[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and above[j + 1]:
            j += 1
        k = i + int(np.argmax(score[i : j + 1]))
        onset = start + i * HOP / SR
        if last is None or onset - last > min_gap:
            last = onset
            end = start + (j * HOP + NPERSEG) / SR
            hits.append((onset, end, float(score[k]), float(bonus[k]), k))
        i = j + 1
    return hits, last


def audio_tracks(path):
    """Number of audio streams FFmpeg can see in the file."""
    r = subprocess.run(
        [ffmpeg(), "-hide_banner", "-nostdin", "-i", str(path)],
        capture_output=True,
        creationflags=FLAGS,
    )
    text = r.stderr.decode("utf-8", errors="replace")
    return len(re.findall(r"^\s*Stream #0:\d+.*?: Audio:", text, flags=re.MULTILINE))


def _stream_args(tracks):
    """FFmpeg options producing 16-bit mono tracks interleaved sample by sample."""
    if len(tracks) == 1:
        return ["-map", f"0:a:{tracks[0]}", "-ac", "1", "-ar", str(SR)]
    graph = ";".join(
        f"[0:a:{i}]aresample={SR},aformat=sample_fmts=s16:channel_layouts=mono[a{i}]"
        for i in tracks
    )
    graph += ";" + "".join(f"[a{i}]" for i in tracks) + f"amerge=inputs={len(tracks)}[out]"
    return ["-filter_complex", graph, "-map", "[out]"]


def _scan_tracks(path, tracks, threshold, info, cancel, progress):
    """Stream the given tracks through FFmpeg once and score them together.

    Returns (hits, decoded_samples) where each hit is
    (onset, end, strength_db, secondary_db, track_index). When several tracks
    are scanned, the strongest reading at each moment wins.
    """
    lanes = len(tracks)
    want = CHUNK_SEC * SR * 2 * lanes
    with tempfile.TemporaryFile() as errors:
        p = subprocess.Popen(
            [
                ffmpeg(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                str(path),
                "-vn",
                "-sn",
                "-dn",
                *_stream_args(tracks),
                "-f",
                "s16le",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=errors,
            creationflags=FLAGS,
        )
        finished = threading.Event()

        def watch():
            while not finished.wait(0.1):
                if cancel.is_set():
                    if p.poll() is None:
                        p.terminate()
                    return

        threading.Thread(target=watch, daemon=True).start()
        hits = []
        tail = np.zeros((0, lanes), np.float32)
        pos = 0  # sample index of tail[0] within the file
        decoded = 0
        last = None
        continued = False
        start = time.monotonic()
        try:
            while True:
                if cancel.is_set():
                    raise Cancelled()
                raw = p.stdout.read(want)
                if not raw:
                    break
                usable = len(raw) // (2 * lanes) * (2 * lanes)
                block = np.frombuffer(raw[:usable], np.int16).astype(np.float32) / 32768
                block = block.reshape(-1, lanes)
                decoded += len(block)
                piece = np.concatenate([tail, block])
                windows = (len(piece) - NPERSEG) // HOP + 1
                consumed = 0
                if windows > 0:
                    best = best_bonus = best_lane = None
                    for lane in range(lanes):
                        score, bonus = score_frames(piece[:, lane])
                        if best is None:
                            best, best_bonus = score, bonus
                            best_lane = np.zeros(len(score), int)
                        else:
                            better = score > best
                            best = np.where(better, score, best)
                            best_bonus = np.where(better, bonus, best_bonus)
                            best_lane = np.where(better, lane, best_lane)
                    found, last = onsets(best, best_bonus, threshold, pos / SR, last, continued=continued)
                    continued = bool(best[-1] > threshold)
                    for onset, end, strength, secondary, k in found:
                        hits.append((onset, end, strength, secondary, tracks[int(best_lane[k])]))
                    # Keep just enough samples so the next chunk's first window
                    # starts exactly HOP after this chunk's last one.
                    consumed = windows * HOP
                tail = piece[consumed:]
                pos += consumed
                progress(
                    min(decoded / SR / info["duration"], 1),
                    decoded / SR,
                    time.monotonic() - start,
                )
            code = p.wait()
            if cancel.is_set():
                raise Cancelled()
            if code:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors="replace")[-1800:])
            if decoded == 0:
                raise ValueError("No audio could be decoded from this recording.")
            if decoded / SR < info["duration"] - 1:
                raise ValueError(
                    f'Audio decoding stopped early at {timestamp(decoded/SR)} of {timestamp(info["duration"])}. Scan incomplete; no finished results returned.'
                )
        finally:
            finished.set()
            if p.poll() is None:
                p.terminate()
                p.wait()
            p.stdout.close()
    return hits, decoded


def scan_audio(
    path,
    threshold=DEFAULT_THRESHOLD,
    track=None,
    cancel=None,
    progress=lambda *a: None,
):
    """Find kill-confirm sounds. Returns (events, info, stats) like engine.scan.

    ``track`` selects the audio stream: a zero-based index, ``ALL_TRACKS`` to
    scan every stream in one pass (slower; the strongest reading per moment
    wins), or None for automatic mode, which scans the first stream and only
    checks the remaining streams when nothing was found there. ``progress``
    receives (fraction, seconds_scanned, elapsed_seconds) and restarts from
    zero if the automatic fallback pass runs.
    """
    if not math.isfinite(threshold) or not 3 <= threshold <= 40:
        raise ValueError("Use a sound sensitivity between 3 and 40 dB.")
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise Cancelled()
    info = probe(path)
    count = audio_tracks(path)
    if count < 1:
        raise ValueError(
            "This recording has no audio track. Record game audio, or switch Detection settings to notification-text matching."
        )
    if track == ALL_TRACKS:
        passes = [list(range(count))]
    elif track is None:
        passes = [[0]] + ([list(range(1, count))] if count > 1 else [])
    else:
        track = int(track)
        if not 0 <= track < count:
            raise ValueError(f"Audio track {track + 1} does not exist; this recording has {count}.")
        passes = [[track]]
    started = time.monotonic()
    scanned = []
    hits = []
    for tracks in passes:
        hits, decoded = _scan_tracks(path, tracks, threshold, info, cancel, progress)
        scanned.extend(tracks)
        if hits:
            break
    events = [
        dict(
            seconds=round(onset, 3),
            end=round(end, 3),
            confidence=round(min(1.0, max(0.0, strength / FULL_CONFIDENCE_DB)), 4),
            strength_db=round(strength, 1),
            secondary_db=round(secondary, 1),
            audio_track=lane,
            title=f"Kill confirmed {i+1:03}",
        )
        for i, (onset, end, strength, secondary, lane) in enumerate(hits)
    ]
    hits_per_track = {}
    for *_, lane in hits:
        hits_per_track[lane] = hits_per_track.get(lane, 0) + 1
    stats = dict(
        method="audio",
        samples=decoded,
        decoded_seconds=decoded / SR,
        elapsed=time.monotonic() - started,
        threshold=threshold,
        min_gap=MIN_GAP,
        audio_tracks=count,
        scanned_tracks=scanned,
        hits_per_track=hits_per_track,
    )
    return events, info, stats
