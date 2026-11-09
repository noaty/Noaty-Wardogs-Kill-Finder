import os, sys, threading, queue, json, math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk
import cv2
from runtime_setup import install_ffmpeg, RUNTIME
from engine import scan, remux, marker_files, unique, timestamp, Cancelled, ffmpeg
from audio import scan_audio, audio_tracks, ALL_TRACKS, DEFAULT_THRESHOLD as AUDIO_THRESHOLD

import preferences
from review_switches import RowSwitches
from verification import verify_candidates, included_events
from highlights import export_highlights, segments

RESOURCE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
FINDER = (
    Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
) / "OBS Highlight Finder.html"
VERSION = "1.3.0"
METHODS = ("Audio + visual check (recommended)", "Kill sound (audio only)", "Notification text (video only)")
SETTINGS = (
    Path(os.environ.get("APPDATA", str(Path.home() / ".config")))
    / "Noaty Kill Finder"
    / "settings.json"
)


class App:
    def __init__(self):
        if (RUNTIME / "ffmpeg.exe").is_file():
            os.environ["IMAGEIO_FFMPEG_EXE"] = str(RUNTIME / "ffmpeg.exe")
        try:
            saved = json.loads(SETTINGS.read_text(encoding="utf-8"))
            binary = saved.get("ffmpeg", "")
            if binary and Path(binary).is_file():
                os.environ["IMAGEIO_FFMPEG_EXE"] = binary
        except (OSError, ValueError):
            pass
        self.root = TkinterDnD.Tk()
        self.root.title("NOATY Kill Finder - " + VERSION)
        self.root.geometry(
            f"{min(1280,self.root.winfo_screenwidth()-60)}x{min(900,self.root.winfo_screenheight()-100)}"
        )
        self.root.minsize(800, 600)
        self.root.configure(bg="#0a1015")
        self.video = None
        self.events = []
        self.original = []
        self.info = {}
        self.stats = {}
        self.busy = False
        self.messages = queue.Queue()
        self.cancel = threading.Event()
        self.photo = None
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#0a1015", foreground="#ecf3f7")
        style.configure("TFrame", background="#0a1015")
        style.configure("TLabel", background="#0a1015", foreground="#ecf3f7")
        style.configure("TButton", padding=(14, 9), borderwidth=0, background="#1d2b35", foreground="white")
        style.map("TButton", background=[("active", "#304654"), ("disabled", "#222a34")])
        style.configure(
            "Primary.TButton",
            background="#c1f985",
            foreground="#112719",
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Treeview",
            background="#111a22",
            fieldbackground="#111a22",
            foreground="#ecf3f7",
            rowheight=36,
        )
        style.configure("Treeview.Heading", background="#26343f", foreground="white")
        style.map("Primary.TButton", background=[("disabled", "#26343f"), ("active", "#d6ffac"), ("!disabled", "#c1f985")], foreground=[("disabled", "#71818c"), ("!disabled", "#112719")])
        style.configure("Horizontal.TProgressbar", background="#c1f985", troughcolor="#1d2b35", borderwidth=0)
        style.configure("TCombobox", padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", "#16232d")], foreground=[("readonly", "#ecf3f7")])
        style.configure("TEntry", fieldbackground="#16232d", foreground="white")
        style.configure("TCombobox", fieldbackground="#16232d", foreground="white")
        style.configure("TLabelframe", background="#0a1015", bordercolor="#26343f")
        style.configure("TLabelframe.Label", background="#0a1015", foreground="#c1f985")
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(
            header,
            text="NOATY  /  KILL FINDER     1.3 AUDIO UPDATE",
            foreground="#c1f985",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        self.newbtn = ttk.Button(
            header, text="+ NEW CLIP", command=self.new_clip
        )
        self.newbtn.pack(side="right")
        ttk.Label(outer, text="Your kills. Already marked.", font=("Segoe UI", 28, "bold")).pack(
            anchor="w", pady=(5, 8)
        )
        ttk.Label(
            outer,
            text="Find the moments. Review your kills. Export a highlight reel.",
        ).pack(anchor="w")
        self.drop = tk.Label(
            outer,
            text="Drop a recording here, or click to choose one",
            bg="#111a22",
            fg="#c1f985",
            font=("Segoe UI", 13, "bold"),
            height=2,
            relief="solid",
            bd=1,
            cursor="hand2",
        )
        self.drop.pack(fill="x", pady=10)
        self.drop.bind("<Button-1>", lambda e: self.pick())
        self.drop.drop_target_register(DND_FILES)
        self.drop.dnd_bind("<<Drop>>", self.on_drop)
        self.filetext = tk.StringVar(
            value="MP4, MOV or MKV | No uploads | Original recording stays untouched"
        )
        ttk.Label(outer, textvariable=self.filetext, wraplength=1030).pack(anchor="w")
        tools = ttk.Frame(outer)
        tools.pack(fill="x", pady=10)
        self.scanbtn = ttk.Button(
            tools, text="SCAN FOR KILLS", style="Primary.TButton", command=self.start_scan
        )
        self.scanbtn.pack(side="left")
        self.cancelbtn = ttk.Button(tools, text="Cancel", command=self.cancel.set, state="disabled")
        self.cancelbtn.pack(side="left", padx=8)
        self.method = tk.StringVar(value=METHODS[0])
        self.audio_threshold = tk.StringVar(value=f"{AUDIO_THRESHOLD:g}")
        self.track = tk.StringVar(value="Auto")
        self.threshold = tk.StringVar(value="0.78")
        self.scale = tk.StringVar(value="Auto")
        for key, value in preferences.load(SETTINGS).items():
            getattr(self, key).set(value)
        self.settingsbtn = ttk.Button(header, text="Detection settings", command=self.settings)
        self.settingsbtn.pack(side="right", padx=8)
        self.methodbox = ttk.Combobox(tools, textvariable=self.method, values=METHODS, state="readonly", width=35)
        self.methodbox.pack(side="right")
        ttk.Label(tools, text="DETECTION METHOD", foreground="#92a4b2").pack(side="right", padx=12)
        self.progress = ttk.Progressbar(outer, maximum=100)
        self.progress.pack(fill="x", pady=(0, 8))
        self.status = tk.StringVar(
            value="Choose a recording to get started. Audio + visual checking is ready."
        )
        ttk.Label(outer, textvariable=self.status, wraplength=1030).pack(anchor="w")
        middle = ttk.Frame(outer)
        middle.pack(fill="both", expand=True, pady=14)
        right = ttk.Frame(middle)
        right.pack(side="left", fill="both", expand=True)
        left = ttk.Frame(middle, width=455)
        left.pack(side="right", fill="both", padx=(18, 0))
        left.pack_propagate(False)
        ttk.Label(right, text="FRAME PREVIEW", foreground="#92a4b2", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))
        self.resultcount = tk.StringVar(value="DETECTED MOMENTS  /  0")
        ttk.Label(left, textvariable=self.resultcount, foreground="#c1f985", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))
        self.tree = ttk.Treeview(
            left, columns=("time", "title", "score", "keep"), show="headings", selectmode="extended"
        )
        self.tree.heading("time", text="Marker time")
        self.tree.heading("title", text="Notification")
        self.tree.heading("score", text="Signal")
        self.tree.column("time", width=125, stretch=False)
        self.tree.column("title", width=115)
        self.tree.column("score", width=65, stretch=False)
        self.tree.heading("keep", text="Export")
        self.tree.column("keep", width=90, stretch=False)
        self.tree.tag_configure("flagged", foreground="#ffca75")
        self.tree.bind("<ButtonRelease-1>", self.toggle_candidate)
        self.tree.bind("<space>", self.toggle_candidate)
        self.clearflagsbtn = ttk.Button(left, text="Remove all OFF", command=self.remove_flagged)
        self.clearflagsbtn.pack(anchor="e", pady=(0, 6))
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.preview)
        self.switches = RowSwitches(self.tree, lambda: self.events, self.toggle_row)
        self.previewlabel = tk.Label(
            right, text="Select a result to inspect its video frame", bg="#0d151c", fg="#92a4b2"
        )
        self.previewlabel.pack(fill="both", expand=True)
        self.previewtime = tk.StringVar(value="Frame preview")
        ttk.Label(right, textvariable=self.previewtime).pack(anchor="w", pady=6)
        edits = ttk.Frame(outer)
        edits.pack(fill="x")
        self.removebtn = ttk.Button(edits, text="Remove selected", command=self.remove)
        self.removebtn.pack(side="left")
        self.restorebtn = ttk.Button(edits, text="Restore results", command=self.restore)
        self.restorebtn.pack(side="left", padx=8)
        self.manual = tk.StringVar()
        self.addbtn = ttk.Button(edits, text="+ Manual marker", command=self.manual_marker)
        self.addbtn.pack(side="right")
        export = ttk.Frame(outer)
        export.pack(fill="x", pady=(8, 0))
        self.exportbtn = ttk.Button(
            export, text="Save video with markers", command=self.export
        )
        self.exportbtn.pack(side="left")
        self.savebtn = ttk.Button(export, text="Export timestamps", command=self.save)
        self.savebtn.pack(side="left", padx=8)
        ttk.Button(export, text="Open marker viewer", command=self.open_finder).pack(side="right")
        ttk.Label(
            outer,
            text="NOATY KILL FINDER  /  LOCAL PROCESSING                                     Audio detection contributed by whiskysix",
            foreground="#c1f985",
            wraplength=1030,
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="Amber = unverified. Export switch: ON includes, OFF excludes. Remove all flagged removes excluded rows; Restore results undoes it.",
            foreground="#92a4b2",
            wraplength=740,
        ).pack(anchor="w", pady=(5, 0))
        clips = ttk.Frame(outer)
        clips.pack(fill="x", before=export, pady=(14, 4))
        self.clipsbtn = ttk.Button(clips, text="EXPORT KILL HIGHLIGHTS", style="Primary.TButton", command=self.export_clips)
        self.clipsbtn.pack(side="right")
        self.clip_before = tk.StringVar(value="5")
        self.clip_after = tk.StringVar(value="5")
        self.clip_gap = tk.StringVar(value="60")
        self.clip_inputs = []
        for label, variable in [("Before (s)", self.clip_before), ("After (s)", self.clip_after), ("Keep together (s)", self.clip_gap)]:
            ttk.Label(clips, text=label).pack(side="left", padx=(10, 4))
            entry = ttk.Entry(clips, textvariable=variable, width=5)
            entry.pack(side="left")
            self.clip_inputs.append(entry)
        self.set_busy(False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.poll)
        if len(sys.argv) > 1:
            self.root.after(200, lambda: self.set_video(sys.argv[1]))

    def settings(self):
        if self.busy:
            return
        draft = {key: tk.StringVar(value=getattr(self, key).get()) for key in preferences.DEFAULTS}
        dialog = tk.Toplevel(self.root)
        dialog.title("Detection settings")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        box = ttk.Frame(dialog, padding=20)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Detection method").pack(anchor="w")
        ttk.Combobox(
            box, textvariable=draft["method"], values=METHODS, state="readonly", width=34
        ).pack(anchor="w", pady=(4, 0))
        audio = ttk.LabelFrame(box, text="Kill sound", padding=10)
        audio.pack(fill="x", pady=(14, 0))
        ttk.Label(
            audio,
            text="Audio finds candidates; the default mode then checks nearby frames. Unverified results stay OFF for review. Audio-only skips the image check.",
            wraplength=420,
        ).pack(anchor="w")
        ttk.Label(audio, text=f"Sensitivity in dB - default {AUDIO_THRESHOLD:g}").pack(
            anchor="w", pady=(10, 4)
        )
        ttk.Entry(audio, textvariable=draft["audio_threshold"], width=10).pack(anchor="w")
        ttk.Label(audio, text="Lower values catch quieter chimes but can add false matches.").pack(
            anchor="w", pady=(4, 0)
        )
        ttk.Label(audio, text="Audio track").pack(anchor="w", pady=(10, 4))
        tracks = 8
        if self.video:
            try:
                tracks = max(1, audio_tracks(self.video))
            except Exception:
                pass
        ttk.Combobox(
            audio,
            textvariable=draft["track"],
            values=["Auto", "All tracks"] + [str(i + 1) for i in range(tracks)],
            state="readonly",
            width=12,
        ).pack(anchor="w")
        ttk.Label(
            audio,
            text="Auto scans the first track and checks the others only when nothing is found there. All tracks is slower.",
            wraplength=420,
        ).pack(anchor="w", pady=(4, 0))
        video = ttk.LabelFrame(box, text="Notification text", padding=10)
        video.pack(fill="x", pady=(14, 0))
        ttk.Label(
            video,
            text="Matches the KILL CONFIRMED text frame by frame. Much slower; use it for recordings without game audio. Auto checks HUD sizes from 50% to 200% and adjusts for low-resolution text.",
            wraplength=420,
        ).pack(anchor="w")
        ttk.Label(video, text="Extra HUD scale (only needed for other UI sizes)").pack(
            anchor="w", pady=(10, 4)
        )
        ttk.Combobox(
            video,
            textvariable=draft["scale"],
            values=["Auto", "75%", "85%", "90%", "100%", "110%", "125%", "150%"],
            state="readonly",
        ).pack(anchor="w")
        ttk.Label(video, text="Match threshold - default 0.78").pack(anchor="w", pady=(10, 4))
        ttk.Entry(video, textvariable=draft["threshold"], width=10).pack(anchor="w")
        ttk.Label(video, text="Lower values may catch faint text but can add false matches.").pack(
            anchor="w", pady=(4, 0)
        )
        def reset():
            for key, value in preferences.DEFAULTS.items():
                draft[key].set(value)

        def save():
            try:
                values = preferences.save(SETTINGS, {key: value.get() for key, value in draft.items()})
            except (OSError, ValueError) as error:
                messagebox.showerror("Settings not saved", str(error), parent=dialog)
                return
            for key, value in values.items():
                getattr(self, key).set(value)
            self.status.set("Detection settings saved for future launches.")
            dialog.destroy()

        actions = ttk.Frame(box)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Reset defaults", command=reset).pack(side="left")
        ttk.Button(actions, text="SAVE", style="Primary.TButton", command=save).pack(side="right")
        ttk.Label(box, text="Reset restores the recommended values. Save applies and remembers them.", foreground="#92a4b2", wraplength=420).pack(anchor="w", pady=(8, 0))
        dialog.grab_set()

    def manual_marker(self):
        value = simpledialog.askstring(
            "Manual marker", "Time (HH:MM:SS or seconds):", parent=self.root
        )
        if value is not None:
            self.manual.set(value)
            self.add()
            self.set_busy(False)

    def pick(self):
        if self.busy:
            return
        p = filedialog.askopenfilename(
            title="Choose WARDOGS recording",
            filetypes=[("Videos", "*.mp4 *.mov *.mkv *.m4v"), ("All files", "*.*")],
        )
        if p:
            self.set_video(p)

    def on_drop(self, e):
        if not self.busy:
            paths = self.root.tk.splitlist(e.data)
            if paths:
                self.set_video(paths[0])

    def set_video(self, p):
        path = Path(p)
        if not path.is_file():
            messagebox.showerror("Video missing", "Choose a finished video file.")
            return
        if self.busy:
            return
        self.new_clip()
        self.video = path
        self.events = []
        self.original = []
        self.info = {}
        self.fill()
        self.filetext.set(str(path))
        self.drop.config(text=path.name)
        self.status.set("Ready to scan.")
        self.previewlabel.config(image="", text="Select a result to inspect its video frame")
        self.photo = None

    def new_clip(self):
        if self.busy:
            return
        self.video = None
        self.events = []
        self.original = []
        self.info = {}
        self.stats = {}
        self.fill()
        self.cancel.clear()
        self.progress["value"] = 0
        self.manual.set("")
        self.previewlabel.config(image="", text="Select a result to inspect its video frame")
        self.photo = None
        self.previewtime.set("Frame preview")
        self.set_busy(False)
        self.drop.config(text="Drop a recording here, or click to choose one")
        self.filetext.set("MP4, MOV or MKV | No uploads | Original recording stays untouched")
        self.status.set("Ready for a new clip. Drop a recording above or click to choose one.")

    def set_busy(self, b):
        self.busy = b
        self.methodbox.config(state="disabled" if b else "readonly")
        self.clearflagsbtn.config(state="disabled" if b else "normal")
        for entry in self.clip_inputs:
            entry.config(state="disabled" if b else "normal")
        for button in [
            self.settingsbtn,
            self.newbtn,
            self.scanbtn,
            self.exportbtn,
            self.clipsbtn,
            self.savebtn,
            self.removebtn,
            self.restorebtn,
            self.addbtn,
        ]:
            button.config(state="disabled" if b else "normal")
        self.cancelbtn.config(state="normal" if b else "disabled")
        if not b:
            for button in [self.exportbtn, self.clipsbtn, self.savebtn]:
                button.config(state="normal" if included_events(self.events) else "disabled")
            for button in [self.removebtn, self.restorebtn]:
                button.config(state="normal" if self.events else "disabled")
            self.addbtn.config(state="normal" if self.info else "disabled")

    def start_scan(self):
        if self.busy:
            return
        if not self.video:
            self.pick()
            return
        needs_setup = False
        try:
            ffmpeg()
        except RuntimeError:
            if not messagebox.askyesno(
                "One-time setup",
                "Download the video scanner component now? This downloads FFmpeg from the pinned imageio-ffmpeg package on PyPI. Your videos are never uploaded. After setup, scanning works offline.",
            ):
                return
            needs_setup = True
        hybrid = self.method.get() == METHODS[0]
        by_sound = self.method.get() != METHODS[2]
        try:
            if hybrid:
                threshold = float(self.threshold.get())
                scale = 1.0 if self.scale.get() == "Auto" else float(self.scale.get().strip("%"))/100
                if not .5 <= threshold <= .99 or not math.isfinite(scale) or scale <= 0:
                    raise ValueError()
            if by_sound:
                audio_threshold = float(self.audio_threshold.get())
                if not 3 <= audio_threshold <= 40:
                    raise ValueError()
                choice = self.track.get()
                if choice == "Auto":
                    track = None
                elif choice == "All tracks":
                    track = ALL_TRACKS
                else:
                    track = int(choice) - 1
            else:
                threshold = float(self.threshold.get())
                scale = (
                    1.0 if self.scale.get() == "Auto" else float(self.scale.get().strip("%")) / 100
                )
                if not 0.5 <= threshold <= 0.99:
                    raise ValueError()
        except ValueError:
            messagebox.showerror(
                "Settings",
                "Use a sound sensitivity between 3 and 40 dB."
                if by_sound
                else "Use a threshold between 0.50 and 0.99.",
            )
            return
        self.cancel.clear()
        self.set_busy(True)
        self.progress["value"] = 0
        self.status.set(
            "Listening for kill-confirm sounds..." if by_sound else "Scanning the notification area..."
        )
        video = self.video

        def report(fraction, t, elapsed):
            self.messages.put(
                (
                    "progress",
                    fraction,
                    f"Scanned {timestamp(t)} | {t/max(elapsed,.01):.1f}x playback speed",
                )
            )

        def work():
            try:
                if needs_setup:
                    install_ffmpeg(
                        self.cancel,
                        lambda f: self.messages.put(
                            ("progress", f, "One-time setup: downloading video scanner...")
                        ),
                    )
                if by_sound:
                    result = scan_audio(
                        video, audio_threshold, track, cancel=self.cancel, progress=report
                    )
                else:
                    result = scan(
                        video,
                        RESOURCE / "template.png",
                        threshold,
                        scale,
                        cancel=self.cancel,
                        progress=report,
                    )
                if hybrid:
                    events, info, stats = result
                    self.messages.put(("progress", 0, "Checking images around audio candidates..."))
                    events, elapsed = verify_candidates(video, events, info, RESOURCE / "template.png", threshold=threshold, scale=scale, cancel=self.cancel,
                        progress=lambda f,n,total: self.messages.put(("progress",f,f"Visual check {n}/{total} audio candidates...")))
                    stats.update(method="hybrid", visual_check_seconds=elapsed, elapsed=stats['elapsed']+elapsed)
                    result = events, info, stats
                self.messages.put(("scanned", result))
            except Cancelled:
                self.messages.put(("cancelled",))
            except Exception as e:
                self.messages.put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                msg = self.messages.get_nowait()
                if msg[0] == "progress":
                    self.progress["value"] = msg[1] * 100
                    self.status.set(msg[2])
                elif msg[0] == "scanned":
                    self.events, self.info, self.stats = msg[1]
                    self.original = [e.copy() for e in self.events]
                    self.fill()
                    self.set_busy(False)
                    self.progress["value"] = 100
                    detail = ""
                    if self.stats.get("method") == "audio":
                        checked = self.stats.get("scanned_tracks", [])
                        detail = f" Audio track{'s' if len(checked) != 1 else ''} checked: {', '.join(str(t + 1) for t in checked)}."
                    if not self.events and self.stats.get("method") == "audio":
                        detail += " No chimes found: try All tracks, or switch to Notification text if game audio is muted or filtered."
                    self.status.set(
                        f"Scanned full video ({timestamp(self.stats['decoded_seconds'])}). Found {len(self.events)} candidates in {self.stats['elapsed']:.1f} seconds.{detail} {len(included_events(self.events))} included; {len(self.events)-len(included_events(self.events))} flagged/excluded. Use each Export switch to include or exclude."
                    )
                elif msg[0] == "exported":
                    self.set_busy(False)
                    self.progress["value"] = 100
                    self.status.set("Ready: " + str(msg[1]))
                    messagebox.showinfo(
                        "Marked video ready",
                        "Drop this video into OBS Highlight Finder:\n\n"
                        + str(msg[1])
                        + "\n\nThe original was not changed.",
                    )
                elif msg[0] == "highlights":
                    self.set_busy(False)
                    self.progress["value"] = 100
                    self.status.set("Highlights ready: " + str(msg[1]))
                    messagebox.showinfo("Highlights ready", "Your edited video is ready:\n\n" + str(msg[1]) + "\n\nOriginal recording unchanged.")
                elif msg[0] == "cancelled":
                    self.set_busy(False)
                    self.status.set("Cancelled. Original recording unchanged.")
                elif msg[0] == "error":
                    self.set_busy(False)
                    self.status.set("Could not finish: " + msg[1])
                    messagebox.showerror("Kill Finder", msg[1])
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def fill(self):
        self.resultcount.set(f"MOMENTS {len(self.events)}  /  EXPORT {len(included_events(self.events))}")
        self.tree.delete(*self.tree.get_children())
        self.events.sort(key=lambda e: e["seconds"])
        for i, e in enumerate(self.events):
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                tags=("flagged",) if e.get("verified") is False else (),
                values=(
                    timestamp(e["seconds"]),
                    e["title"],
                    (
                        f"{e['strength_db']:.1f} dB"
                        if "strength_db" in e
                        else f"{e.get('confidence',1):.0%}"
                    ),
                    "",
                ),
            )

    def preview(self, event=None):
        selected = self.tree.selection()
        if not selected or not self.video:
            return
        e = self.events[int(selected[0])]
        t = e.get("preview_seconds", e["seconds"] + 0.25)
        c = cv2.VideoCapture(str(self.video))
        c.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = c.read()
        c.release()
        if ok:
            im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            im.thumbnail(
                (
                    max(100, self.previewlabel.winfo_width() - 8),
                    max(80, self.previewlabel.winfo_height() - 8),
                )
            )
            self.photo = ImageTk.PhotoImage(im)
            self.previewlabel.config(image=self.photo, text="")
            self.previewtime.set(
                "Frame at " + timestamp(t) + " | marker " + timestamp(e["seconds"])
            )

    def toggle_candidate(self, event):
        if self.busy:
            return
        if event.keysym == "space":
            selected = self.tree.selection()
            row = selected[0] if selected else ""
        else:
            if self.tree.identify_column(event.x) != "#4":
                return
            row = self.tree.identify_row(event.y)
        if row:
            self.toggle_row(row)

    def toggle_row(self, row):
        if self.busy or not self.tree.exists(row):
            return
        item = self.events[int(row)]
        item['included'] = not item.get('included', True)
        self.resultcount.set(f"MOMENTS {len(self.events)}  /  EXPORT {len(included_events(self.events))}")
        self.tree.selection_set(row)
        self.set_busy(False)

    def remove_flagged(self):
        if self.busy:
            return
        self.events = included_events(self.events)
        self.fill()
        self.set_busy(False)

    def remove(self):
        for i in sorted(map(int, self.tree.selection()), reverse=True):
            del self.events[i]
        self.fill()
        self.set_busy(False)

    def restore(self):
        self.events = [e.copy() for e in self.original]
        self.fill()
        self.set_busy(False)

    def add(self):
        if not self.info:
            messagebox.showinfo("Scan first", "Scan a video before adding manual markers.")
            return
        try:
            parts = list(map(float, self.manual.get().split(":")))
            t = sum(x * 60**i for i, x in enumerate(reversed(parts)))
            if not 0 <= t < self.info["duration"]:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Time", "Enter a time within the recording.")
            return
        self.events.append(dict(seconds=t, title="Manual highlight", confidence=1))
        self.fill()
        self.manual.set("")

    def save(self):
        if not included_events(self.events):
            messagebox.showinfo("No markers", "Scan a recording first.")
            return
        folder = filedialog.askdirectory(
            initialdir=str(self.video.parent), title="Save small timestamp files"
        )
        if folder:
            try:
                p = marker_files(self.video, included_events(self.events), self.info, self.stats, folder)
                self.status.set("Saved JSON, CSV and TXT: " + str(p.parent))
            except Exception as e:
                messagebox.showerror("Save failed", str(e))

    def export(self):
        if not included_events(self.events):
            messagebox.showinfo("No markers", "Scan and review the recording first.")
            return
        dest = unique(self.video.with_name(self.video.stem + " - KILL MARKERS.mp4"))
        p = filedialog.asksaveasfilename(
            initialdir=str(dest.parent),
            initialfile=dest.name,
            defaultextension=".mp4",
            filetypes=[("Chaptered MP4", "*.mp4")],
        )
        if not p:
            return
        self.cancel.clear()
        self.set_busy(True)
        self.progress["value"] = 0
        self.status.set("Copying streams and adding chapters. No re-encoding...")
        events = included_events(self.events)

        def work():
            try:
                out = remux(
                    self.video,
                    events,
                    self.info,
                    p,
                    self.cancel,
                    lambda f: self.messages.put(("progress", f, "Writing marked copy...")),
                )
                marker_files(self.video, events, self.info, self.stats, Path(p).parent)
                self.messages.put(("exported", out))
            except Cancelled:
                self.messages.put(("cancelled",))
            except Exception as e:
                self.messages.put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def export_clips(self):
        if self.busy or not included_events(self.events):
            return
        try:
            before, after, gap = [float(v.get()) for v in (self.clip_before, self.clip_after, self.clip_gap)]
            if any(not math.isfinite(v) or v < 0 for v in (before, after, gap)) or before + after <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Highlight timing", "Enter non-negative seconds. Before and after cannot both be zero.")
            return
        folder = Path.home() / "Desktop"
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
                    folder = Path(os.path.expandvars(winreg.QueryValueEx(key, "Desktop")[0]))
            except OSError:
                pass
        if not folder.is_dir():
            folder = Path.home()
        dest = unique(folder / (self.video.stem + " - KILL HIGHLIGHTS.mp4"))
        p = filedialog.asksaveasfilename(initialdir=str(folder), initialfile=dest.name,
            defaultextension=".mp4", filetypes=[("Highlights video", "*.mp4")])
        if not p:
            return
        events = included_events(self.events)
        video, info = self.video, self.info.copy()
        self.cancel.clear()
        self.set_busy(True)
        self.progress["value"] = 0
        self.status.set("Editing kill highlights... Original video stays untouched.")
        def work():
            try:
                out = export_highlights(video, events, info, p, self.cancel,
                    lambda f: self.messages.put(("progress", f, f"Exporting highlights... {f:.0%}")),
                    before=before, after=after, gap=gap)
                self.messages.put(("highlights", out))
            except Cancelled:
                self.messages.put(("cancelled",))
            except Exception as e:
                self.messages.put(("error", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def open_finder(self):
        p = FINDER if FINDER.exists() else Path(sys.executable).parent / "OBS Highlight Finder.html"
        if p.exists():
            os.startfile(p)
        else:
            messagebox.showinfo(
                "Finder", "Open your OBS Highlight Finder.html and drop in the marked video."
            )

    def close(self):
        if self.busy:
            self.cancel.set()
            self.status.set("Cancelling safely...")
            self.root.after(300, self.close)
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()


