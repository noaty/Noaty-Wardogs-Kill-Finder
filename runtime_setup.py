"""One-time, user-approved FFmpeg setup from the pinned PyPI dependency."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import zipfile

from engine import Cancelled

RUNTIME = (
    Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "Noaty Kill Finder" / "runtime"
)


def install_ffmpeg(cancel, progress):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(
        "https://pypi.org/pypi/imageio-ffmpeg/0.7.0/json", timeout=30
    ) as response:
        metadata = json.load(response)
    wheel = next(f for f in metadata["urls"] if f["filename"].endswith("win_amd64.whl"))
    if not wheel["url"].startswith("https://files.pythonhosted.org/"):
        raise ValueError("Unexpected download host.")
    expected = wheel["digests"]["sha256"]
    destination = RUNTIME / "ffmpeg.exe"
    with tempfile.TemporaryDirectory(dir=RUNTIME) as directory:
        archive = Path(directory) / "runtime.whl"
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(wheel["url"], timeout=30) as response, archive.open(
            "wb"
        ) as out:
            while True:
                if cancel.is_set():
                    raise Cancelled()
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > 150 * 1024 * 1024:
                    raise ValueError("Runtime download exceeded expected size.")
                digest.update(chunk)
                out.write(chunk)
                progress(min(size / max(wheel["size"], 1), 1))
        if digest.hexdigest() != expected:
            raise ValueError("Runtime checksum did not match; download discarded.")
        with zipfile.ZipFile(archive) as wheel_zip:
            member = next(
                i
                for i in wheel_zip.infolist()
                if i.filename.startswith("imageio_ffmpeg/binaries/ffmpeg-")
                and i.filename.endswith(".exe")
            )
            if member.file_size > 200 * 1024 * 1024:
                raise ValueError("Unexpected runtime size.")
            binary = Path(directory) / "ffmpeg.exe"
            binary.write_bytes(wheel_zip.read(member))
            if cancel.is_set():
                raise Cancelled()
            os.replace(binary, destination)
    os.environ["IMAGEIO_FFMPEG_EXE"] = str(destination)
    return destination
