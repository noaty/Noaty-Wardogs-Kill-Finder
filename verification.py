"""Verify only short windows around audio candidates, never the full video."""
import threading
import time
import cv2
from engine import Cancelled, hud_templates, notification_matches, highpass


def included_events(events):
    return [e.copy() for e in events if e.get('included', True)]


def verify_candidates(path, events, info, template_path, threshold=.78, scale=1., cancel=None, progress=lambda *a: None):
    cancel = cancel or threading.Event()
    started = time.monotonic()
    reference = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if reference is None:
        raise ValueError('Notification template is missing.')
    templates = hud_templates(reference, info['height'], scale)
    # Fine raster-size variants catch glyph widths between the broad HUD steps.
    for factor in (.95, .975, .99, 1.01, 1.025, 1.05):
        templates.append(highpass(cv2.resize(reference, None, fx=factor*scale, fy=factor*scale, interpolation=cv2.INTER_CUBIC)))
    capture = cv2.VideoCapture(str(path))
    results = []
    try:
        for i, original in enumerate(events):
            event = original.copy()
            hits = 0
            decoded = 0
            for offset in (.15, .45, .8, -.15, 1.2) + tuple(n / 10 for n in range(-5, 21) if n not in (8,12)):
                if cancel.is_set():
                    raise Cancelled()
                t = max(0., min(info['duration']-.01, event['seconds']+offset))
                capture.set(cv2.CAP_PROP_POS_MSEC, t*1000)
                ok, frame = capture.read()
                if not ok:
                    continue
                decoded += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                height, width = gray.shape
                gray = cv2.resize(gray, (max(1, round(width*1080/height)),1080), interpolation=cv2.INTER_CUBIC)
                if gray.shape[1] < 540:
                    pad = 540-gray.shape[1]
                    gray = cv2.copyMakeBorder(gray,0,0,pad//2,pad-pad//2,cv2.BORDER_CONSTANT)
                x = (gray.shape[1]-540)//2
                scores = notification_matches(gray[540:920,x:x+540],templates,threshold)
                if scores:
                    hits += 1
                    event['visual_confidence'] = max(event.get('visual_confidence',0),max(scores))
                    if hits >= 2:
                        event['preview_seconds'] = t
                        break
            verified = hits >= 2
            event.update(verified=verified, included=verified, review_reason='' if verified else ('Text not confirmed' if decoded else 'Preview could not decode'))
            event['title'] = ('Kill confirmed' if verified else 'Check audio candidate') + f' {i+1:03}'
            results.append(event)
            progress((i+1)/max(1,len(events)),i+1,len(events))
    finally:
        capture.release()
    return results, time.monotonic()-started
