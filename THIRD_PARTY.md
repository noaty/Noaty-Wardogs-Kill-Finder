# Third-party components

NOATY's copyright notice does not replace third-party licenses. Installed package license files and available `.dist-info` notices are copied into the Windows package's `third-party-licenses` directory at build time.

| Component | Upstream / source and license information |
|---|---|
| Python / Tk | https://www.python.org/psf/license/ and https://www.tcl.tk/software/tcltk/license.html |
| NumPy | https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| OpenCV Python | https://github.com/opencv/opencv-python — includes third-party codec notices |
| Pillow | https://github.com/python-pillow/Pillow/blob/main/LICENSE |
| tkinterdnd2 / TkDnD | https://github.com/Eliav2/tkinterdnd2 |
| imageio-ffmpeg | https://github.com/imageio/imageio-ffmpeg |
| PyInstaller (build tool) | https://pyinstaller.org/en/stable/license.html |

The public package **does not redistribute the standalone FFmpeg executable**. On first use, users may authorize a download from the pinned imageio-ffmpeg wheel on PyPI, or provide their own FFmpeg installation. See https://ffmpeg.org/legal.html for that project's licensing information. Source installations may receive an FFmpeg binary from the separately installed imageio-ffmpeg wheel.

`template.png` is a small WARDOGS HUD text reference used for notification matching. The game's name and imagery belong to their respective rights holders; they are not relicensed by this project.
