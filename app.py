import os, sys, threading, queue, json, math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk
import cv2
from runtime_setup import install_ffmpeg, RUNTIME
from engine import scan, remux, marker_files, unique, timestamp, Cancelled, ffmpeg

from highlights import export_highlights, segments

RESOURCE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
FINDER = (
    Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
) / "OBS Highlight Finder.html"
VERSION = "1.2.1"
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
        self.root.title("NOATY Kill Finder Â· " + VERSION)
        self.root.geometry(
            f"{min(1120,self.root.winfo_screenwidth()-60)}x{min(820,self.root.winfo_screenheight()-100)}"
        )
        self.root.minsize(800, 600)
        self.root.configure(bg="#101720")
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
        style.configure(".", font=("Segoe UI", 10), background="#101720", foreground="#edf2f8")
        style.configure("TFrame", background="#101720")
        style.configure("TLabel", background="#101720", foreground="#edf2f8")
        style.configure("TButton", padding=10, background="#293d50", foreground="white")
        style.map("TButton", background=[("active", "#3c5970"), ("disabled", "#222a34")])
        style.configure(
            "Primary.TButton",
            background="#adf5c5",
            foreground="#112719",
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Treeview",
            background="#1a2635",
            fieldbackground="#1a2635",
            foreground="#e4edf8",
            rowheight=30,
        )
        style.configure("Treeview.Heading", background="#304258", foreground="white")
        style.configure("Horizontal.TProgressbar", background="#adf5c5")
        style.configure("TEntry", fieldbackground="#233244", foreground="white")
        style.configure("TCombobox", fieldbackground="#233244", foreground="white")
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(
            header,
            text="NOATY  /  LOCAL VIDEO TOOLS",
            foreground="#adf5c5",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        self.newbtn = ttk.Button(
            header, text="+ NEW CLIP", style="Primary.TButton", command=self.new_clip
        )
        self.newbtn.pack(side="right")
        ttk.Label(outer, text="Your kills. Already marked.", font=("Segoe UI", 24, "bold")).pack(
            anchor="w", pady=(5, 8)
        )
        ttk.Label(
            outer,
            text="1  Choose a video     â†’     2  Scan & review     â†’     3  Export highlights or save markers",
        ).pack(anchor="w")
        self.drop = tk.Label(
            outer,
            text="Drop a recording here, or click to choose one",
            bg="#1c2a3b",
            fg="#adf5c5",
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
            value="MP4, MOV or MKV â€¢ No uploads â€¢ Original recording stays untouched"
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
        self.threshold = tk.StringVar(value="0.78")
        self.scale = tk.StringVar(value="Auto")
        self.settingsbtn = ttk.Button(tools, text="Detection settings", command=self.settings)
        self.settingsbtn.pack(side="right")
        self.progress = ttk.Progressbar(outer, maximum=100)
        self.progress.pack(fill="x", pady=(0, 8))
        self.status = tk.StringVar(
            value="Choose a recording to get started. Automatic detection supports standard and 125% notification text."
        )
        ttk.Label(outer, textvariable=self.status, wraplength=1030).pack(anchor="w")
        middle = ttk.Frame(outer)
        middle.pack(fill="both", expand=True, pady=14)
        left = ttk.Frame(middle)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(middle, width=340)
        right.pack(side="right", fill="both", padx=(18, 0))
        right.pack_propagate(False)
        self.tree = ttk.Treeview(
            left, columns=("time", "title", "score"), show="headings", selectmode="extended"
        )
        self.tree.heading("time", text="Marker time")
        self.tree.heading("title", text="Notification")
        self.tree.heading("score", text="Match")
        self.tree.column("time", width=125, stretch=False)
        self.tree.column("title", width=155)
        self.tree.column("score", width=65, stretch=False)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.preview)
        self.previewlabel = tk.Label(
            right, text="Select a result to inspect its video frame", bg="#172330", fg="#b0c1d5"
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
        export.pack(fill="x", before=middle, pady=(8, 0))
        self.exportbtn = ttk.Button(
            export, text="SAVE VIDEO WITH MARKERS", style="Primary.TButton", command=self.export
        )
        self.exportbtn.pack(side="left")
        self.savebtn = ttk.Button(export, text="Export timestamps", command=self.save)
        self.savebtn.pack(side="left", padx=8)
        ttk.Button(export, text="Open marker viewer", command=self.open_finder).pack(side="right")
        ttk.Label(
            outer,
            text="Saves a new MP4 with embedded markers. No re-encoding. Your source stays untouched.",
            foreground="#adf5c5",
            wraplength=1030,
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="Review detections before editing. Hidden or overlapping popups can be missed. Marker times follow the notification, not the shot.",
            foreground="#95a8bf",
            wraplength=740,
        ).pack(anchor="w", pady=(5, 0))
        clips = ttk.Frame(outer)
        clips.pack(fill="x", before=middle, pady=(4, 8))
        self.clipsbtn = ttk.Button(clips, text="EXPORT KILL HIGHLIGHTS", style="Primary.TButton", command=self.export_clips)
        self.clipsbtn.pack(side="left")
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
        dialog = tk.Toplevel(self.root)
        dialog.title("Detection settings")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        box = ttk.Frame(dialog, padding=20)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Auto checks HUD text sizes from 75% to 150% in every frame.").pack(
            anchor="w"
        )
        ttk.Label(box, text="Extra HUD scale (only needed for other UI sizes)").pack(
            anchor="w", pady=(14, 4)
        )
        ttk.Combobox(
            box,
            textvariable=self.scale,
            values=["Auto", "75%", "85%", "90%", "100%", "110%", "125%", "150%"],
            state="readonly",
        ).pack(anchor="w")
        ttk.Label(box, text="Match threshold Â· default 0.78").pack(anchor="w", pady=(14, 4))
        ttk.Entry(box, textvariable=self.threshold, width=10).pack(anchor="w")
        ttk.Label(box, text="Lower values may catch faint text but can add false matches.").pack(
            anchor="w", pady=10
        )
        ttk.Button(box, text="Done", command=dialog.destroy).pack(anchor="e")
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
        self.filetext.set("MP4, MOV or MKV â€¢ No uploads â€¢ Original recording stays untouched")
        self.status.set("Ready for a new clip. Drop a recording above or click to choose one.")

    def set_busy(self, b):
        self.busy = b
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
            for button in [self.exportbtn, self.clipsbtn, self.savebtn, self.removebtn, self.restorebtn]:
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
        try:
            threshold = float(self.threshold.get())
            scale = 1.0 if self.scale.get() == "Auto" else float(self.scale.get().strip("%")) / 100
            if not 0.5 <= threshold <= 0.99:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Settings", "Use a threshold between 0.50 and 0.99.")
            return
        self.cancel.clear()
        self.set_busy(True)
        self.progress["value"] = 0
        self.status.set("Scanning the notification areaâ€¦")
        video = self.video

        def work():
            try:
                if needs_setup:
                    install_ffmpeg(
                        self.cancel,
                        lambda f: self.messages.put(
                            ("progress", f, "One-time setup: downloading video scannerâ€¦")
                        ),
                    )
                result = scan(
                    video,
                    RESOURCE / "template.png",
                    threshold,
                    scale,
                    cancel=self.cancel,
                    progress=lambda fraction, t, elapsed: self.messages.put(
                        (
                            "progress",
                            fraction,
                            f"Scanned {timestamp(t)} â€¢ {t/max(elapsed,.01):.1f}Ã— playback speed",
                        )
                    ),
                )
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
                    self.status.set(
                        f"Scanned full video ({timestamp(self.stats['decoded_seconds'])}). Found {len(self.events)} confirmations in {self.stats['elapsed']:.1f} seconds. Review, then create the marked copy."
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
        self.tree.delete(*self.tree.get_children())
        self.events.sort(key=lambda e: e["seconds"])
        for i, e in enumerate(self.events):
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(timestamp(e["seconds"]), e["title"], f"{e.get('confidence',1):.0%}"),
            )

    def preview(self, event=None):
        selected = self.tree.selection()
        if not selected or not self.video:
            return
        e = self.events[int(selected[0])]
        t = e["seconds"] + 0.25
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
                "Frame at " + timestamp(t) + " â€¢ marker " + timestamp(e["seconds"])
            )

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
        if not self.events:
            messagebox.showinfo("No markers", "Scan a recording first.")
            return
        folder = filedialog.askdirectory(
            initialdir=str(self.video.parent), title="Save small timestamp files"
        )
        if folder:
            try:
                p = marker_files(self.video, self.events, self.info, self.stats, folder)
                self.status.set("Saved JSON, CSV and TXT: " + str(p.parent))
            except Exception as e:
                messagebox.showerror("Save failed", str(e))

    def export(self):
        if not self.events:
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
        self.status.set("Copying streams and adding chapters. No re-encodingâ€¦")
        events = [e.copy() for e in self.events]

        def work():
            try:
                out = remux(
                    self.video,
                    events,
                    self.info,
                    p,
                    self.cancel,
                    lambda f: self.messages.put(("progress", f, "Writing marked copyâ€¦")),
                )
                marker_files(self.video, events, self.info, self.stats, Path(p).parent)
                self.messages.put(("exported", out))
            except Cancelled:
                self.messages.put(("cancelled",))
            except Exception as e:
                self.messages.put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def export_clips(self):
        if self.busy or not self.events:
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
        events = [e.copy() for e in self.events]
        video, info = self.video, self.info.copy()
        self.cancel.clear()
        self.set_busy(True)
        self.progress["value"] = 0
        self.status.set("Editing kill highlightsâ€¦ Original video stays untouched.")
        def work():
            try:
                out = export_highlights(video, events, info, p, self.cancel,
                    lambda f: self.messages.put(("progress", f, f"Exporting highlightsâ€¦ {f:.0%}")),
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
            self.status.set("Cancelling safelyâ€¦")
            self.root.after(300, self.close)
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()

