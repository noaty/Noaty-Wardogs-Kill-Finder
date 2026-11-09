"""Build the public Windows ZIP. Does not bundle the FFmpeg executable."""

import hashlib
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VERSION = "1.3.0"

if sys.platform != "win32":
    raise SystemExit("Build on Windows with Python 3.12 (64-bit).")
os.chdir(ROOT)
build = ROOT / "build"
build.mkdir(exist_ok=True)
spec = build / "Noaty Kill Finder.spec"
spec.write_text(
    '''from PyInstaller.utils.hooks import collect_all
datas = [(r"'''
    + str(ROOT / "template.png")
    + '''", '.')]
binaries = []
hiddenimports = []
for package in ('tkinterdnd2', 'imageio_ffmpeg'):
    d, b, h = collect_all(package)
    datas += d; binaries += b; hiddenimports += h
a = Analysis([r"'''
    + str(ROOT / "app.py")
    + """"], pathex=[], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, hookspath=[],
             hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
def standalone_ffmpeg(row):
    name = row[0].replace('\\\\', '/').split('/')[-1].lower()
    return name.startswith('ffmpeg') and name.endswith('.exe')
a.binaries = [x for x in a.binaries if not standalone_ffmpeg(x)]
a.datas = [x for x in a.datas if not standalone_ffmpeg(x)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Noaty Kill Finder',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Noaty Kill Finder')
""",
    encoding="utf-8",
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(build / "pyinstaller"),
        str(spec),
    ],
    check=True,
)
output = ROOT / "dist" / "Noaty Kill Finder"
for name in (
    "OBS Highlight Finder.html",
    "START HERE.txt",
    "README.md",
    "COPYRIGHT.txt",
    "THIRD_PARTY.md",
    "CHANGELOG.md",
):
    shutil.copy2(ROOT / name, output / name)
licenses = output / "third-party-licenses"
for package in ("numpy", "opencv-python-headless", "Pillow", "imageio-ffmpeg", "tkinterdnd2"):
    distribution = importlib.metadata.distribution(package)
    for entry in distribution.files or []:
        if any(word in str(entry).lower() for word in ("license", "copying", "notice")):
            source = distribution.locate_file(entry)
            if source.is_file():
                dest = licenses / package / str(entry).replace("..", "_")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
for license_name in ("LICENSE.txt", "LICENSE"):
    source = Path(sys.base_prefix) / license_name
    if source.is_file():
        licenses.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, licenses / ("Python-" + license_name))
if any(
    p.name.lower().startswith("ffmpeg") and p.suffix.lower() == ".exe" for p in output.rglob("*")
):
    raise RuntimeError("Standalone FFmpeg must not be included in the public package.")
archive = Path(
    shutil.make_archive(
        str(ROOT / "dist" / f"Noaty-Kill-Finder-Windows-v{VERSION}"),
        "zip",
        ROOT / "dist",
        output.name,
    )
)
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix(".sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
print(f"Built {archive.name} ({archive.stat().st_size // 1024 // 1024} MiB)")

