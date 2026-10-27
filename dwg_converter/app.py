"""DWG 轉圖檔：拖曳 .dwg 到視窗，轉成 JPG 或 PNG。"""

import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from tkinterdnd2 import DND_FILES, TkinterDnD

from . import converter

SIZE_PRESETS = {"標準 6000 px": 6000, "高 12000 px": 12000, "超高 20000 px": 20000}
UI_FONT_CANDIDATES = ("Microsoft JhengHei UI", "PingFang TC", "Noto Sans CJK TC", "Noto Sans TC", "WenQuanYi Zen Hei")


@dataclass
class Job:
    iid: str
    dwg: Path
    out: Path
    color: bool
    long_side_px: int
    auto_crop: bool


def output_path(dwg: Path, folder: str, color: bool, ext: str) -> Path:
    suffix = "" if color else "-黑白"
    return Path(folder or dwg.parent) / f"{dwg.stem}{suffix}.{ext}"


def format_elapsed(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def pick_ui_font() -> str:
    available = set(tkfont.families())
    for name in UI_FONT_CANDIDATES:
        if name in available:
            return name
    return tkfont.nametofont("TkDefaultFont").actual("family")


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def reveal_path(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


class App:
    def __init__(self, root: TkinterDnD.Tk):
        self.root = root
        self.jobs: queue.Queue[Job] = queue.Queue()
        self.events: queue.Queue[tuple] = queue.Queue()
        self.running: dict[str, tuple[float, str]] = {}
        self.current_proc: subprocess.Popen | None = None
        self.outputs: dict[str, Path] = {}

        family = pick_ui_font()
        root.title("DWG 轉圖檔")
        root.geometry("820x600")
        root.minsize(680, 520)
        root.option_add("*Font", (family, 10))
        ttk.Style().configure("Treeview", rowheight=26, font=(family, 10))
        ttk.Style().configure("Drop.TLabel", font=(family, 12), relief="groove")

        self.color = tk.StringVar(value="color")
        self.fmt = tk.StringVar(value="jpg")
        self.size = tk.StringVar(value="高 12000 px")
        self.auto_crop = tk.BooleanVar(value=True)
        self.out_mode = tk.StringVar(value="same")
        self.out_folder = tk.StringVar()

        self.build_ui()
        threading.Thread(target=self.worker, daemon=True).start()
        root.after(200, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)

        drop = ttk.Label(
            main,
            text="把 .dwg 檔案拖曳到這裡\n或點擊選擇檔案",
            style="Drop.TLabel",
            cursor="hand2",
            anchor="center",
            justify="center",
        )
        drop.pack(fill="x", ipady=28)
        drop.bind("<Button-1>", lambda _e: self.pick_files())
        drop.drop_target_register(DND_FILES)
        drop.dnd_bind("<<Drop>>", self.on_drop)
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self.on_drop)

        opts = ttk.LabelFrame(main, text="輸出設定", padding=10)
        opts.pack(fill="x", pady=(12, 0))
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="色彩").grid(row=0, column=0, sticky="w", pady=3)
        color_row = ttk.Frame(opts)
        color_row.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(color_row, text="彩色（依圖層）", variable=self.color, value="color").pack(side="left")
        ttk.Radiobutton(color_row, text="黑白", variable=self.color, value="mono").pack(side="left", padx=(12, 0))

        ttk.Label(opts, text="格式").grid(row=1, column=0, sticky="w", pady=3)
        fmt_row = ttk.Frame(opts)
        fmt_row.grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(fmt_row, text="JPG", variable=self.fmt, value="jpg").pack(side="left")
        ttk.Radiobutton(fmt_row, text="PNG", variable=self.fmt, value="png").pack(side="left", padx=(12, 0))

        ttk.Label(opts, text="解析度（長邊）").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(opts, textvariable=self.size, values=list(SIZE_PRESETS), state="readonly", width=16).grid(
            row=2, column=1, sticky="w"
        )

        ttk.Label(opts, text="輸出位置").grid(row=3, column=0, sticky="w", pady=3)
        out_row = ttk.Frame(opts)
        out_row.grid(row=3, column=1, sticky="ew")
        out_row.columnconfigure(2, weight=1)
        ttk.Radiobutton(out_row, text="與原檔同資料夾", variable=self.out_mode, value="same").grid(row=0, column=0)
        ttk.Radiobutton(
            out_row, text="指定", variable=self.out_mode, value="custom", command=self.pick_folder_if_empty
        ).grid(row=0, column=1, padx=(12, 0))
        ttk.Entry(out_row, textvariable=self.out_folder).grid(row=0, column=2, sticky="ew", padx=(6, 6))
        ttk.Button(out_row, text="瀏覽", command=self.pick_folder).grid(row=0, column=3)

        ttk.Checkbutton(
            opts, text="自動取景（排除離群的零星物件，圖面會放得比較大）", variable=self.auto_crop
        ).grid(row=4, column=1, sticky="w", pady=(6, 0))

        bar = ttk.Frame(main)
        bar.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(bar, text="開啟圖片", command=self.open_image).pack(side="left")
        ttk.Button(bar, text="開啟所在資料夾", command=self.open_folder).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="清除已完成", command=self.clear_finished).pack(side="left", padx=(8, 0))
        self.status = ttk.Label(bar, text="拖入檔案後會自動開始轉換")
        self.status.pack(side="right")

        list_frame = ttk.Frame(main)
        list_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.tree = ttk.Treeview(
            list_frame, columns=("file", "status", "output"), show="headings", selectmode="browse", height=5
        )
        for col, text, width in (("file", "檔案", 260), ("status", "狀態", 150), ("output", "輸出", 300)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self.open_image())

    def pick_files(self) -> None:
        paths = filedialog.askopenfilenames(title="選擇 DWG 檔案", filetypes=[("DWG 檔案", "*.dwg")])
        self.add_files(paths)

    def pick_folder(self) -> None:
        folder = filedialog.askdirectory(title="選擇輸出資料夾")
        if folder:
            self.out_folder.set(folder)
            self.out_mode.set("custom")

    def pick_folder_if_empty(self) -> None:
        if not self.out_folder.get():
            self.pick_folder()
            if not self.out_folder.get():
                self.out_mode.set("same")

    def on_drop(self, event) -> None:
        self.add_files(self.root.tk.splitlist(event.data))

    def add_files(self, paths) -> None:
        added = skipped = 0
        for raw in paths:
            path = Path(raw)
            if path.suffix.lower() != ".dwg" or not path.is_file():
                skipped += 1
                continue
            color = self.color.get() == "color"
            folder = self.out_folder.get() if self.out_mode.get() == "custom" else ""
            out = output_path(path, folder, color, self.fmt.get())
            iid = self.tree.insert("", "end", values=(path.name, "等待中", ""))
            self.jobs.put(Job(iid, path, out, color, SIZE_PRESETS[self.size.get()], self.auto_crop.get()))
            added += 1
        if skipped:
            self.status.config(text=f"已略過 {skipped} 個不是 .dwg 的項目")
        elif added:
            self.status.config(text=f"已加入 {added} 個檔案")

    def worker(self) -> None:
        while True:
            job = self.jobs.get()
            started = time.monotonic()
            try:
                result = converter.convert(
                    job.dwg,
                    job.out,
                    color=job.color,
                    long_side_px=job.long_side_px,
                    auto_crop=job.auto_crop,
                    progress=lambda stage, iid=job.iid: self.events.put(("stage", iid, stage)),
                    on_process=lambda proc: setattr(self, "current_proc", proc),
                )
                self.events.put(("done", job.iid, result, time.monotonic() - started))
            except Exception as exc:
                self.events.put(("error", job.iid, str(exc) or type(exc).__name__, traceback.format_exc()))
            finally:
                self.current_proc = None

    def poll(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind, iid = event[0], event[1]
            if not self.tree.exists(iid):
                continue
            if kind == "stage":
                started = self.running[iid][0] if iid in self.running else time.monotonic()
                self.running[iid] = (started, event[2])
            elif kind == "done":
                self.running.pop(iid, None)
                self.outputs[iid] = event[2]
                status = f"完成（{format_elapsed(event[3])}）"
                self.tree.item(iid, values=(self.tree.set(iid, "file"), status, str(event[2])))
            elif kind == "error":
                self.running.pop(iid, None)
                self.tree.item(iid, values=(self.tree.set(iid, "file"), f"失敗：{event[2]}", ""))

        now = time.monotonic()
        for iid, (t0, stage) in self.running.items():
            if self.tree.exists(iid):
                self.tree.set(iid, "status", f"{stage}… {format_elapsed(now - t0)}")
        active = len(self.running) + self.jobs.qsize()
        if active:
            self.status.config(text=f"處理中，剩餘 {active} 個")
        elif self.outputs:
            self.status.config(text="全部完成，雙擊清單項目可開啟圖片")
        self.root.after(500, self.poll)

    def selected_output(self) -> Path | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("DWG 轉圖檔", "請先在清單中選一個項目")
            return None
        out = self.outputs.get(selection[0])
        if not out or not out.exists():
            messagebox.showinfo("DWG 轉圖檔", "這個項目還沒有輸出檔案")
            return None
        return out

    def open_image(self) -> None:
        if out := self.selected_output():
            open_path(out)

    def open_folder(self) -> None:
        if out := self.selected_output():
            reveal_path(out)

    def clear_finished(self) -> None:
        for iid in self.tree.get_children():
            status = self.tree.set(iid, "status")
            if status.startswith(("完成", "失敗")):
                self.tree.delete(iid)
                self.outputs.pop(iid, None)

    def on_close(self) -> None:
        if self.current_proc and self.current_proc.poll() is None:
            self.current_proc.terminate()
        self.root.destroy()
        os._exit(0)


def run_cli(args: list[str]) -> int:
    dwg, out = Path(args[0]), Path(args[1])
    mono = "mono" in args[2:]
    try:
        converter.convert(dwg, out, color=not mono)
        return 0
    except Exception:
        out.with_suffix(".error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 1


def main() -> None:
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if len(sys.argv) >= 4 and sys.argv[1] == "--cli":
        sys.exit(run_cli(sys.argv[2:]))
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = TkinterDnD.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
