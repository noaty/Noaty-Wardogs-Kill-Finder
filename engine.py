"""Offline fixed-HUD matching and lossless chapter remux. No model or network calls."""

from pathlib import Path
import subprocess, threading, tempfile, os, json, csv, time, shutil
import cv2
import numpy as np
import imageio_ffmpeg


class Cancelled(Exception):
    pass


FLAGS = 0x08000000 if os.name == "nt" else 0
cv2.setNumThreads(2)


_verified_ffmpeg = {}


def validate_ffmpeg(candidate):
    """Accept only an executable that actually runs, invalidating replaced files."""
    if not candidate:
        return None
    resolved = shutil.which(str(candidate)) or str(candidate)
    path = Path(resolved)
    try:
        stat = path.stat()
        key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
        if key not in _verified_ffmpeg:
            result = subprocess.run([str(path), "-version"], capture_output=True,
                                    timeout=15, creationflags=FLAGS)
            if result.returncode != 0 or b"ffmpeg version" not in result.stdout.lower():
                return None
            _verified_ffmpeg[key] = True
        return str(path.resolve())
    except (OSError, subprocess.SubprocessError):
        return None


def ffmpeg():
    bundled = Path(__file__).resolve().parent / "ffmpeg.exe"
    portable = Path(__import__("sys").executable).parent / "ffmpeg.exe"
    for candidate in (os.environ.get("IMAGEIO_FFMPEG_EXE"), portable, bundled,
                      shutil.which("ffmpeg")):
        valid = validate_ffmpeg(candidate)
        if valid:
            return valid
    try:
        valid = validate_ffmpeg(imageio_ffmpeg.get_ffmpeg_exe())
        if valid:
            return valid
    except (RuntimeError, OSError):
        pass
    raise RuntimeError("FFmpeg is missing or cannot run. Install the scanner component and retry.")


def timestamp(t):
    ms = max(0, round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def probe(path):
    c = cv2.VideoCapture(str(path))
    if not c.isOpened():
        raise ValueError(
            "Cannot open this video. Make sure it is fully downloaded and the recording has stopped."
        )
    fps = c.get(cv2.CAP_PROP_FPS)
    frames = c.get(cv2.CAP_PROP_FRAME_COUNT)
    w = c.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = c.get(cv2.CAP_PROP_FRAME_HEIGHT)
    c.release()
    if fps <= 0 or frames <= 0 or h <= 0:
        raise ValueError("Video duration or dimensions are unavailable.")
    return dict(duration=frames / fps, fps=fps, width=int(w), height=int(h))


def highpass(a):
    return cv2.subtract(a, cv2.GaussianBlur(a, (0, 0), 2))


def group_hits(hits, rate=10, threshold=0.78, gap=0.45, min_hits=2):
    events = []
    current = None
    for t, score in hits:
        if score < threshold:
            continue
        if current is None or t - current["last"] > gap:
            if current and current["hits"] >= min_hits:
                events.append(current)
            current = {"seconds": t, "last": t, "hits": 1, "confidence": score}
        else:
            current["last"] = t
            current["hits"] += 1
            current["confidence"] = max(current["confidence"], score)
    if current and current["hits"] >= min_hits:
        events.append(current)
    return [
        dict(
            seconds=round(e["seconds"], 3),
            end=round(e["last"], 3),
            confidence=round(e["confidence"], 4),
            title=f"Kill confirmed {i+1:03}",
        )
        for i, e in enumerate(events)
    ]


def notification_matches(frame, template, threshold):
    # Match boxes, not top-left rows: differently sized templates can describe
    # the same text at slightly different coordinates.
    templates = template if isinstance(template, list) else [template]
    filtered = highpass(frame)
    candidates = []
    for candidate in templates:
        h, w = candidate.shape
        if h > frame.shape[0] or w > frame.shape[1]:
            continue
        result = cv2.matchTemplate(filtered, candidate, cv2.TM_CCOEFF_NORMED)
        for _ in range(100):
            _, score, _, (x, y) = cv2.minMaxLoc(result)
            if score < threshold:
                break
            candidates.append((float(score), x, y, w, h))
            result[max(0,y-h//2):y+h//2+1, max(0,x-w//2):x+w//2+1] = -1
    kept = []
    for box in sorted(candidates, reverse=True):
        score, x, y, w, h = box
        duplicate = False
        for _, bx, by, bw, bh in kept:
            overlap_x = max(0, min(x+w,bx+bw)-max(x,bx))
            overlap_y = max(0, min(y+h,by+bh)-max(y,by))
            if overlap_x > .5*min(w,bw) and overlap_y > .5*min(h,bh):
                duplicate = True
                break
        if not duplicate:
            kept.append(box)
    return [box[0] for box in kept]


def hud_templates(reference, height, scale=1.0):
    """Normalize HUD size and imitate detail lost in sub-1080p recordings."""
    scales = sorted(set([.5, .625, .75, .85, .9, 1., 1.1, 1.25, 1.5, 1.75, 2., float(scale)]))
    result = []
    for factor in scales:
        candidate = cv2.resize(reference, None, fx=factor, fy=factor,
                               interpolation=cv2.INTER_CUBIC)
        result.append(candidate)
        if height < 1080:
            # Resizing an isolated glyph loses subpixel alignment. Simulate
            # downsampling on a padded canvas at several pixel alignments.
            phases = min(4, int(np.ceil(1080/height)))
            h, w = candidate.shape
            for dy in range(phases):
                for dx in range(phases):
                    canvas = np.zeros((108, 432), np.uint8)
                    y, x = 40+dy, 40+dx
                    canvas[y:y+h, x:x+w] = candidate
                    small = cv2.resize(canvas, (round(432*height/1080), round(108*height/1080)),
                                       interpolation=cv2.INTER_AREA)
                    restored = cv2.resize(small, (432,108), interpolation=cv2.INTER_CUBIC)
                    result.append(restored[y:y+h, x:x+w])
    return [highpass(t) for t in result]


def group_notifications(frames, rate=10, threshold=0.78):
    # Each extra simultaneously visible line starts another notification event.
    # Ranking by confidence keeps an old row moving upward from counting again.
    events = []
    for layer in range(max((len(scores) for _, scores in frames), default=0)):
        events.extend(
            group_hits(
                [(t, scores[layer] if len(scores) > layer else 0) for t, scores in frames],
                rate,
                threshold,
            )
        )
    events.sort(key=lambda e: e["seconds"])
    for i, e in enumerate(events):
        e["title"] = f"Kill confirmed {i+1:03}"
    return events


def scan(
    path, template_path, threshold=0.78, scale=1.0, rate=10, cancel=None, progress=lambda *a: None
):
    cancel = cancel or threading.Event()
    info = probe(path)
    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise ValueError("Notification template is missing.")
    template = hud_templates(template, info["height"], scale)
    # Height normalization preserves wide/tall aspect ratios. Pad very narrow
    # videos so the center search crop is always valid.
    vf = f"setpts=PTS-STARTPTS,fps={rate}:start_time=0,scale=-2:1080,pad=max(iw\\,540):1080:(ow-iw)/2:0,crop=540:380:(iw-540)/2:540,format=gray"
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
                "-an",
                "-sn",
                "-dn",
                "-vf",
                vf,
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
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
        i = 0
        start = time.monotonic()
        try:
            while True:
                if cancel.is_set():
                    raise Cancelled()
                raw = p.stdout.read(540 * 380)
                if not raw:
                    break
                if len(raw) != 540 * 380:
                    raise ValueError("Decoder returned an incomplete frame.")
                frame = np.frombuffer(raw, np.uint8).reshape(380, 540)
                scores = notification_matches(frame, template, threshold)
                hits.append((i / rate, scores))
                i += 1
                if i % 10 == 0:
                    progress(
                        min(i / rate / info["duration"], 1), i / rate, time.monotonic() - start
                    )
            code = p.wait()
            if cancel.is_set():
                raise Cancelled()
            if code:
                errors.seek(0)
                raise ValueError(errors.read().decode(errors="replace")[-1800:])
            if i == 0:
                raise ValueError("No frames could be decoded.")
            if i / rate < info["duration"] - max(1, 2 / rate):
                raise ValueError(
                    f'Decoding stopped early at {timestamp(i/rate)} of {timestamp(info["duration"])}. Scan incomplete; no finished results returned.'
                )
        finally:
            finished.set()
            if p.poll() is None:
                p.terminate()
                p.wait()
            p.stdout.close()
    return (
        group_notifications(hits, rate, threshold),
        info,
        dict(
            samples=i,
            decoded_seconds=i / rate,
            elapsed=time.monotonic() - start,
            threshold=threshold,
            template_scale=scale,
            sample_rate=rate,
        ),
    )


def original_chapters(path):
    r = subprocess.run(
        [
            ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-map_metadata",
            "0",
            "-map_chapters",
            "0",
            "-f",
            "ffmetadata",
            "pipe:1",
        ],
        capture_output=True,
        creationflags=FLAGS,
    )
    if r.returncode:
        raise ValueError(
            "Could not read existing chapters: " + r.stderr.decode(errors="replace")[-1000:]
        )
    chapters = []
    for block in r.stdout.decode("utf-8", errors="replace").split("[CHAPTER]")[1:]:
        kv = {}
        for line in block.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                kv[k] = v
        try:
            num, den = map(int, kv.get("TIMEBASE", "1/1000").split("/"))
            seconds = int(kv["START"]) * num / den
            title = (
                kv.get("title", "Existing OBS marker")
                .replace("\\=", "=")
                .replace("\\;", ";")
                .replace("\\#", "#")
                .replace("\\\\", "\\")
            )
            chapters.append(dict(seconds=seconds, title=title))
        except (ValueError, KeyError, ZeroDivisionError):
            raise ValueError("Existing chapter metadata could not be preserved safely.")
    return chapters


def unique(path):
    p = Path(path)
    candidate = p
    i = 2
    while candidate.exists():
        candidate = p.with_name(p.stem + f" ({i})" + p.suffix)
        i += 1
    return candidate


def marker_files(video, events, info, stats, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = Path(video).stem + " - kill markers"
    base = unique(folder / (stem + ".json"))
    payload = dict(
        version=1,
        source=str(Path(video).resolve()),
        source_size=Path(video).stat().st_size,
        video=info,
        scan=stats,
        markers=events,
    )
    base.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    csvpath = base.with_suffix(".csv")
    txt = base.with_suffix(".txt")
    with csvpath.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Number", "Chapter", "Marker time", "Start watching", "Seconds"])
        for i, e in enumerate(events):
            w.writerow(
                [
                    i + 1,
                    e["title"],
                    timestamp(e["seconds"]),
                    timestamp(max(0, e["seconds"] - 10)),
                    e["seconds"],
                ]
            )
    txt.write_text(
        Path(video).name
        + "\nKill-confirmation notification timestamps (10-second lead-in)\n\n"
        + "\n".join(
            f"{timestamp(e['seconds'])} | {e['title']} | Start watching {timestamp(max(0,e['seconds']-10))}"
            for e in events
        ),
        encoding="utf-8",
    )
    return base


def remux(video, events, info, output, cancel=None, progress=lambda *a: None):
    cancel = cancel or threading.Event()
    video = Path(video).resolve()
    output = Path(output).resolve()
    if video == output or output.exists():
        raise ValueError(
            "Choose a new output filename. The source recording will not be overwritten."
        )
    if not events:
        raise ValueError("No markers to write.")
    if shutil.disk_usage(output.parent).free < video.stat().st_size * 1.03:
        raise ValueError(
            "Not enough free space for a marked copy. Save timestamp files instead, or choose another drive."
        )
    chapters = original_chapters(video) + [
        dict(seconds=e["seconds"], title=e["title"]) for e in events
    ]
    if not any(c["seconds"] < 0.001 for c in chapters):
        chapters.append(dict(seconds=0, title="Recording start"))
    chapters.sort(key=lambda c: c["seconds"])
    merged = []
    for c in chapters:
        if not 0 <= c["seconds"] < info["duration"]:
            continue
        if merged and abs(c["seconds"] - merged[-1]["seconds"]) < 0.001:
            merged[-1]["title"] += " / " + c["title"]
        else:
            merged.append(c.copy())

    def escape(t):
        return (
            str(t)
            .replace("\\", "\\\\")
            .replace("\n", " ")
            .replace("\r", " ")
            .replace("=", "\\=")
            .replace(";", "\\;")
            .replace("#", "\\#")
        )

    text = ";FFMETADATA1\n"
    for i, c in enumerate(merged):
        end = merged[i + 1]["seconds"] if i + 1 < len(merged) else info["duration"]
        text += f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(c['seconds']*1000)}\nEND={max(round(c['seconds']*1000)+1,round(end*1000))}\ntitle={escape(c['title'])}\n"
    fd, metadata = tempfile.mkstemp(suffix=".ffmetadata")
    os.close(fd)
    Path(metadata).write_text(text, encoding="utf-8")
    partial = output.with_name(output.stem + ".partial-" + str(time.time_ns()) + output.suffix)
    try:
        with tempfile.TemporaryFile() as errors:
            args = [
                ffmpeg(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-n",
                "-i",
                str(video),
                "-f",
                "ffmetadata",
                "-i",
                metadata,
                "-map",
                "0:v",
                "-map",
                "0:a?",
                "-map",
                "0:s?",
                "-map_metadata",
                "0",
                "-map_chapters",
                "1",
                "-c",
                "copy",
                "-progress",
                "pipe:1",
                "-nostats",
                str(partial),
            ]
            p = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=errors, creationflags=FLAGS, text=True
            )
            finished = threading.Event()

            def watch():
                while not finished.wait(0.1):
                    if cancel.is_set():
                        if p.poll() is None:
                            p.terminate()
                        return

            threading.Thread(target=watch, daemon=True).start()
            try:
                for line in p.stdout:
                    if line.startswith("out_time_us="):
                        try:
                            progress(min(float(line.split("=")[1]) / 1e6 / info["duration"], 1))
                        except ValueError:
                            pass
                code = p.wait()
                if cancel.is_set():
                    raise Cancelled()
                if code:
                    errors.seek(0)
                    raise ValueError(
                        "Could not write a compatible MP4 without re-encoding. "
                        + errors.read().decode(errors="replace")[-1200:]
                    )
            finally:
                finished.set()
                if p.poll() is None:
                    p.terminate()
                    p.wait()
                p.stdout.close()
        written = original_chapters(partial)
        if len(written) != len(merged) or any(
            abs(a["seconds"] - b["seconds"]) > 0.025 for a, b in zip(written, merged)
        ):
            raise ValueError("Chapter verification failed. No final video was created.")
        if output.exists():
            raise ValueError("Output filename became occupied; choose another filename.")
        partial.rename(output)
        return output
    finally:
        Path(metadata).unlink(missing_ok=True)
        partial.unlink(missing_ok=True)

