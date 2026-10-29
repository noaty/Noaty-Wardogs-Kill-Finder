import tempfile
import threading
import unittest
from pathlib import Path

import cv2
import numpy as np

from engine import (
    Cancelled,
    ffmpeg,
    group_notifications,
    highpass,
    notification_matches,
    original_chapters,
    probe,
    remux,
    scan,
)
import subprocess

ROOT = Path(__file__).resolve().parent


class DetectionTests(unittest.TestCase):
    def test_stacked_notifications_and_persistence(self):
        frames = [
            (0, []),
            (0.1, [0.99]),
            (0.2, [0.99]),
            (0.3, [0.99, 0.98]),
            (0.4, [0.99, 0.98]),
            (0.5, [0.99]),
            (0.6, [0.99]),
        ]
        events = group_notifications(frames)
        self.assertEqual([e["seconds"] for e in events], [0.1, 0.3])

    def test_isolated_match_is_not_a_kill(self):
        self.assertEqual(group_notifications([(0, []), (0.1, [0.9]), (0.2, [])]), [])

    def test_separated_notifications(self):
        events = group_notifications([(0, [0.9]), (0.1, [0.9]), (1, []), (2, [0.9]), (2.1, [0.9])])
        self.assertEqual(len(events), 2)

    def test_two_text_sizes_and_two_rows(self):
        reference = cv2.imread(str(ROOT / "template.png"), 0)
        large = cv2.resize(reference, None, fx=1.25, fy=1.25, interpolation=cv2.INTER_CUBIC)
        frame = np.zeros((280, 540), dtype=np.uint8)
        for y, text in [(100, reference), (130, large)]:
            frame[y : y + text.shape[0], 190 : 190 + text.shape[1]] = text
        matches = notification_matches(frame, [highpass(reference), highpass(large)], 0.78)
        self.assertEqual(len(matches), 2)

    def test_blank_frame(self):
        reference = cv2.imread(str(ROOT / "template.png"), 0)
        self.assertEqual(
            notification_matches(np.zeros((280, 540), np.uint8), highpass(reference), 0.78), []
        )


class VideoTests(unittest.TestCase):
    def test_scan_export_and_original_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.mp4"
            subprocess.run(
                [
                    ffmpeg(),
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=1920x1080:r=10:d=2",
                    "-c:v",
                    "mpeg4",
                    str(source),
                ],
                check=True,
                capture_output=True,
            )
            original = source.read_bytes()
            events, info, stats = scan(source, ROOT / "template.png")
            self.assertEqual(events, [])
            self.assertAlmostEqual(stats["decoded_seconds"], 2, delta=0.2)
            markers = [
                dict(seconds=0.5, title="Kill confirmed 001"),
                dict(seconds=1.2, title="Kill confirmed 002"),
            ]
            output = Path(folder) / "marked.mp4"
            remux(source, markers, info, output)
            chapters = original_chapters(output)
            self.assertEqual([round(e["seconds"], 1) for e in chapters], [0, 0.5, 1.2])
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaises(ValueError):
                remux(source, markers, info, source)
            with self.assertRaises(ValueError):
                remux(source, markers, info, output)
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaises(Cancelled):
                scan(source, ROOT / "template.png", cancel=cancelled)


if __name__ == "__main__":
    unittest.main()
