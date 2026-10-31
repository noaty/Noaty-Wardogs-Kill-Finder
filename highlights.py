"""Automatic highlight editing from reviewed kill timestamps."""
import math
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from engine import ffmpeg, probe, FLAGS, Cancelled


def segments(events, duration, before=5, after=5, gap=60):
    if any(not math.isfinite(v) or v < 0 for v in (before, after, gap)) or before + after <= 0:
        raise ValueError('Use non-negative timing values; before and after cannot both be zero.')
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid video duration.')
    times = sorted(set(float(e['seconds']) for e in events))
    if not times or any(not math.isfinite(t) or t < 0 or t >= duration for t in times):
        raise ValueError('Kill timestamps must be inside the video.')
    result = []
    first = last = times[0]
    for t in times[1:]:
        if t - last <= gap or t - before <= last + after:
            last = t
        else:
            result.append((max(0, first-before), min(duration, last+after)))
            first = last = t
    result.append((max(0, first-before), min(duration, last+after)))
    return result


def export_highlights(video, events, info, output, cancel=None, progress=lambda f: None, before=5, after=5, gap=60):
    video, output = Path(video).resolve(), Path(output).resolve()
    if output == video or output.exists():
        raise ValueError('Choose a new output filename. Existing files are never overwritten.')
    if output.suffix.lower() != '.mp4':
        raise ValueError('Save highlights as an MP4 file.')
    cancel = cancel or threading.Event()
    spans = segments(events, info['duration'], before, after, gap)
    total = sum(b-a for a,b in spans)

    def run(args, base, length, weight):
        if cancel.is_set():
            raise Cancelled()
        with tempfile.TemporaryFile() as errors:
            p = subprocess.Popen([ffmpeg(), '-hide_banner', '-nostdin', '-loglevel', 'error',
                '-progress', 'pipe:1', '-nostats', *args], stdout=subprocess.PIPE,
                stderr=errors, text=True, creationflags=FLAGS)
            done = threading.Event()
            def watch():
                while not done.wait(.1):
                    if cancel.is_set():
                        if p.poll() is None: p.terminate()
                        return
            watcher = threading.Thread(target=watch, daemon=True)
            watcher.start()
            try:
                for line in p.stdout:
                    if line.startswith('out_time_us='):
                        try: progress(min(.99, base + weight * max(0, min(1, float(line.split('=')[1])/1e6/length))))
                        except ValueError: pass
                code = p.wait()
                if cancel.is_set(): raise Cancelled()
                if code:
                    errors.seek(0)
                    raise RuntimeError('Video export failed: ' + errors.read().decode(errors='replace')[-1500:])
            finally:
                done.set()
                if p.poll() is None: p.terminate()
                p.wait(); watcher.join(); p.stdout.close()

    with tempfile.TemporaryDirectory(prefix='noaty-highlights-', dir=output.parent) as tmp:
        tmp = Path(tmp)
        elapsed = 0
        for i,(start,end) in enumerate(spans):
            length = end-start
            run(['-ss', str(start), '-i', str(video), '-t', str(length),
                 '-map', '0:v:0', '-map', '0:a?', '-map_metadata', '-1', '-map_chapters', '-1',
                 '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                 '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                 '-c:a', 'aac', '-b:a', '192k', '-avoid_negative_ts', 'make_zero',
                 '-n', str(tmp/f'{i:05}.mp4')], .95*elapsed/total, length, .95*length/total)
            elapsed += length
        listing = tmp/'segments.txt'
        listing.write_text(''.join("file '%05d.mp4'\n" % i for i in range(len(spans))), encoding='utf-8')
        final = tmp/'highlights.mp4'
        run(['-f','concat','-safe','1','-i',str(listing),'-map','0','-c','copy',
             '-movflags','+faststart','-n',str(final)], .95, total, .04)
        actual = probe(final)['duration']
        if abs(actual-total) > max(1, len(spans)*.15):
            raise RuntimeError('Export duration check failed; no finished file was saved.')
        if cancel.is_set(): raise Cancelled()
        if output.exists(): raise ValueError('Output now exists. Choose another filename.')
        os.rename(final, output)
    progress(1)
    return output

