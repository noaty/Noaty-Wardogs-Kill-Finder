import subprocess
import tempfile
import threading
import unittest
import wave
from pathlib import Path

import numpy as np

from audio import (
    ALL_TRACKS,
    HOP,
    NPERSEG,
    PRIMARY,
    SECONDARY,
    SR,
    WINDOW,
    audio_tracks,
    onsets,
    scan_audio,
    score_frames,
)
from engine import Cancelled, ffmpeg

ROOT = Path(__file__).resolve().parent


def ding(at, seconds, amplitude=0.2, seed=0):
    """Quiet background noise with a synthetic kill-confirm chime at ``at`` seconds."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 0.002, int(seconds * SR)).astype(np.float32)
    t = np.arange(int(0.4 * SR)) / SR
    envelope = np.exp(-t / 0.15)
    chime = sum(
        gain * np.sin(2 * np.pi * f * t)
        for f, gain in zip(PRIMARY + SECONDARY, (0.5, 0.5, 0.25, 0.25))
    )
    start = int(at * SR)
    x[start : start + len(t)] += (amplitude * envelope * chime).astype(np.float32)
    return x


def gunshot(x, at, seed=1):
    """Add a loud broadband burst, much louder than any chime."""
    rng = np.random.default_rng(seed)
    start = int(at * SR)
    burst = rng.normal(0, 0.5, int(0.12 * SR)) * np.exp(-np.arange(int(0.12 * SR)) / (0.04 * SR))
    x[start : start + len(burst)] += burst.astype(np.float32)
    return x


def write_wav(path, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def make_video(folder, name, *tracks, seconds=3):
    """Black video with one PCM audio stream per WAV track, so no encoder low-pass."""
    inputs = []
    for i, samples in enumerate(tracks):
        wav = folder / f"{name}-{i}.wav"
        write_wav(wav, samples)
        inputs += ["-i", str(wav)]
    out = folder / f"{name}.mov"
    args = [
        ffmpeg(),
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=320x240:r=10:d={seconds}",
    ]
    args += inputs + ["-map", "0:v"]
    for i in range(len(tracks)):
        args += ["-map", f"{i+1}:a"]
    args += ["-c:v", "mpeg4", "-c:a", "pcm_s16le", "-shortest", str(out)]
    subprocess.run(args, check=True, capture_output=True)
    return out


class ScoringTests(unittest.TestCase):
    def test_window_shape(self):
        self.assertEqual(len(WINDOW), NPERSEG)
        self.assertAlmostEqual(float(WINDOW[0]), 0, places=5)
        self.assertAlmostEqual(float(WINDOW[NPERSEG // 2]), 1, places=5)

    def test_chime_is_prominent_and_gunshot_is_not(self):
        x = gunshot(ding(1.0, 3), 2.0)
        score, bonus = score_frames(x)
        self.assertEqual(len(score), (len(x) - NPERSEG) // HOP + 1)
        hits, _ = onsets(score, bonus, 12)
        self.assertEqual(len(hits), 1)
        onset, end, strength, secondary, _ = hits[0]
        self.assertTrue(0.8 <= onset <= 1.02, onset)
        self.assertGreater(end, onset)
        self.assertGreater(strength, 12)
        self.assertGreater(secondary, 6)
        # The much louder gunshot window itself scores far below threshold.
        shot = int(2.0 * SR / HOP)
        self.assertLess(float(score[shot : shot + 10].max()), 6)

    def test_continuous_tone_is_not_recounted_at_chunk_boundary(self):
        score = np.array([20, 20, 0, 0, 20, 20], np.float32)
        hits, _ = onsets(score, np.zeros_like(score), 12, start=10, last=8, continued=True)
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0][0], 10.04)

    def test_filtered_audio_requires_three_lower_partials(self):
        x = ding(1.0, 3)
        spectrum = np.fft.rfft(x)
        spectrum[np.fft.rfftfreq(len(x), 1/SR) > 16000] = 0
        filtered = np.fft.irfft(spectrum, n=len(x)).astype(np.float32)
        score, bonus = score_frames(filtered)
        hits, _ = onsets(score, bonus, 12)
        self.assertEqual(len(hits), 1)
        t = np.arange(3*SR)/SR
        single = (.2*np.sin(2*np.pi*PRIMARY[0]*t)).astype(np.float32)
        score, bonus = score_frames(single)
        hits, _ = onsets(score, bonus, 12)
        self.assertEqual(hits, [])

    def test_short_input(self):
        score, bonus = score_frames(np.zeros(NPERSEG - 1, np.float32))
        self.assertEqual((len(score), len(bonus)), (0, 0))

    def test_two_chimes_and_minimum_gap(self):
        x = ding(0.5, 4) + ding(2.5, 4, seed=2) + ding(2.8, 4, seed=3)
        score, bonus = score_frames(x)
        hits, _ = onsets(score, bonus, 12)
        # Onsets are the start of the first window containing the chime, so they
        # can lead the chime by up to one window (NPERSEG / SR, about 0.17 s).
        self.assertEqual(len(hits), 2, hits)
        for hit, expected in zip(hits, (0.5, 2.5)):
            self.assertTrue(expected - NPERSEG / SR <= hit[0] <= expected + 0.02, (hit, expected))

    def test_gap_applies_across_chunks(self):
        score = np.array([0, 20, 20, 0, 0, 20, 0], np.float32)
        bonus = np.zeros_like(score)
        first, last = onsets(score[:4], bonus[:4], 12, start=0.0)
        second, _ = onsets(score[4:], bonus[4:], 12, start=4 * HOP / SR, last=last)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        third, _ = onsets(score[4:], bonus[4:], 12, start=10.0, last=last)
        self.assertEqual(len(third), 1)
        self.assertAlmostEqual(third[0][0], 10 + HOP / SR)


class VideoTests(unittest.TestCase):
    def test_scan_single_track(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            video = make_video(folder, "one", gunshot(ding(0.8, 3), 1.9))
            self.assertEqual(audio_tracks(video), 1)
            fractions = []
            events, info, stats = scan_audio(
                video, progress=lambda f, t, elapsed: fractions.append(f)
            )
            self.assertEqual(len(events), 1, events)
            self.assertTrue(0.6 <= events[0]["seconds"] <= 0.82, events[0])
            self.assertEqual(events[0]["title"], "Kill confirmed 001")
            self.assertGreater(events[0]["strength_db"], 12)
            self.assertTrue(0 < events[0]["confidence"] <= 1)
            self.assertEqual(stats["method"], "audio")
            self.assertEqual(stats["scanned_tracks"], [0])
            self.assertEqual(stats["hits_per_track"], {0: 1})
            self.assertAlmostEqual(stats["decoded_seconds"], 3, delta=0.2)
            self.assertAlmostEqual(info["duration"], 3, delta=0.2)
            self.assertTrue(fractions and fractions[-1] >= 0.9)
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaises(Cancelled):
                scan_audio(video, cancel=cancelled)

    def test_track_selection_and_automatic_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            silent = np.random.default_rng(5).normal(0, 0.002, 3 * SR).astype(np.float32)
            video = make_video(folder, "two", silent, ding(1.2, 3))
            self.assertEqual(audio_tracks(video), 2)
            events, _, stats = scan_audio(video, track=0)
            self.assertEqual(events, [])
            self.assertEqual(stats["scanned_tracks"], [0])
            events, _, stats = scan_audio(video, track=1)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["audio_track"], 1)
            events, _, stats = scan_audio(video)
            self.assertEqual(len(events), 1)
            self.assertEqual(stats["scanned_tracks"], [0, 1])
            events, _, stats = scan_audio(video, track=ALL_TRACKS)
            self.assertEqual(len(events), 1)
            self.assertEqual(stats["hits_per_track"], {1: 1})
            with self.assertRaises(ValueError):
                scan_audio(video, track=2)

    def test_no_audio_track(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "mute.mp4"
            subprocess.run(
                [
                    ffmpeg(),
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=320x240:r=10:d=1",
                    "-c:v",
                    "mpeg4",
                    str(video),
                ],
                check=True,
                capture_output=True,
            )
            self.assertEqual(audio_tracks(video), 0)
            with self.assertRaisesRegex(ValueError, "no audio track"):
                scan_audio(video)


if __name__ == "__main__":
    unittest.main()
