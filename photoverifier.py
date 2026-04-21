#!/usr/bin/env python3
"""
PhotoBackup Verifier
Uses SHA-256 checksums to guarantee your backup drive is a perfect mirror.
No file is considered "backed up" unless its hash matches byte-for-byte.
"""

import os
import hashlib
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
from typing import Dict, Optional
import time

CHUNK = 1 << 20  # 1 MB read chunks

DARK_BG     = "#1e1e2e"
PANEL_BG    = "#181825"
TEXT_FG     = "#cdd6f4"
MUTED_FG    = "#6c7086"
GREEN       = "#a6e3a1"
RED         = "#f38ba8"
ORANGE      = "#fab387"
PURPLE      = "#cba6f7"
YELLOW      = "#f9e2af"
SURFACE     = "#313244"
FONT_MONO   = ("Menlo", 10)
FONT_UI     = ("SF Pro Text", 11)
FONT_BIG    = ("SF Pro Display", 22, "bold")


# ─── hashing ────────────────────────────────────────────────────────────────

def sha256_file(path: Path):
    """Return hex digest, or None on any I/O error."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while buf := f.read(CHUNK):
                h.update(buf)
        return h.hexdigest()
    except OSError:
        return None


def scan_dir(root: Path, on_file=None, cancel_event=None) -> Dict[str, Optional[str]]:
    """Walk root, skipping hidden files/dirs. Returns {rel_path: hash_or_None}."""
    out: Dict[str, Optional[str]] = {}
    for dp, dirs, files in os.walk(root):
        if cancel_event and cancel_event.is_set():
            break
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in sorted(files):
            if cancel_event and cancel_event.is_set():
                return out
            if fn.startswith("."):
                continue
            full = Path(dp) / fn
            rel = str(full.relative_to(root))
            if on_file:
                on_file(rel, len(out))
            out[rel] = sha256_file(full)
    return out


def compare_maps(src: dict, dst: dict):
    sk, dk = set(src), set(dst)
    common   = sk & dk
    identical = {k for k in common if src[k] is not None and src[k] == dst[k]}
    changed   = {k: (src[k], dst[k]) for k in common if src[k] != dst[k]}
    missing   = sk - dk
    extra     = dk - sk
    errors    = {k for k in src if src[k] is None} | {k for k in dst if dst[k] is None}
    return identical, changed, missing, extra, errors


# ─── GUI ────────────────────────────────────────────────────────────────────

class PhotoVerifier(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PhotoBackup Verifier")
        self.geometry("860x760")
        self.minsize(720, 640)
        self.configure(bg=DARK_BG)
        self.resizable(True, True)

        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()
        self.src_map: dict = {}
        self.dst_map: dict = {}
        self._busy = False
        self._cancel = threading.Event()

        self._style()
        self._build()

    # ── styles ──────────────────────────────────────────────────────────────

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure("TFrame",      background=DARK_BG)
        s.configure("TLabel",      background=DARK_BG, foreground=TEXT_FG, font=FONT_UI)
        s.configure("TLabelframe", background=DARK_BG, foreground=MUTED_FG,
                    font=("SF Pro Text", 10, "bold"))
        s.configure("TLabelframe.Label", background=DARK_BG, foreground=MUTED_FG)
        s.configure("TEntry",      fieldbackground=SURFACE, foreground=TEXT_FG,
                    insertcolor=TEXT_FG, font=FONT_UI)
        s.configure("TButton",     background=SURFACE, foreground=TEXT_FG,
                    font=FONT_UI, padding=6, relief="flat")
        s.map("TButton",
              background=[("active", "#45475a"), ("disabled", "#2a2a3a")],
              foreground=[("active", TEXT_FG),   ("disabled", MUTED_FG)])

        s.configure("Scan.TButton",   background="#1e4a8a", foreground="white",
                    font=("SF Pro Text", 11, "bold"), padding=8)
        s.configure("Sync.TButton",   background="#7c3a00", foreground="white",
                    font=("SF Pro Text", 11, "bold"), padding=8)
        s.configure("Verify.TButton", background="#1a5c2a", foreground="white",
                    font=("SF Pro Text", 11, "bold"), padding=8)
        s.configure("Cancel.TButton", background="#5c1a1a", foreground="white",
                    font=("SF Pro Text", 11, "bold"), padding=8)
        s.map("Cancel.TButton",
              background=[("active", "#7a2020"), ("disabled", "#2a2a3a")],
              foreground=[("active", "white"),   ("disabled", MUTED_FG)])

        s.configure("TProgressbar", troughcolor=SURFACE, background=GREEN,
                    thickness=6)
        s.configure("Indet.TProgressbar", troughcolor=SURFACE, background=PURPLE,
                    thickness=6)

    # ── layout ──────────────────────────────────────────────────────────────

    def _build(self):
        # ── header
        hdr = tk.Frame(self, bg=PANEL_BG, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="PhotoBackup Verifier", bg=PANEL_BG,
                 fg=TEXT_FG, font=("SF Pro Display", 16, "bold")).pack(side="left", padx=16)
        tk.Label(hdr, text="SHA-256 file integrity checker", bg=PANEL_BG,
                 fg=MUTED_FG, font=("SF Pro Text", 11)).pack(side="left")

        # ── path selectors
        pf = ttk.LabelFrame(self, text="  Drives  ", padding=(12, 8))
        pf.pack(fill="x", padx=14, pady=(10, 4))
        pf.columnconfigure(1, weight=1)

        tk.Label(pf, text="Source / internal drive:", bg=DARK_BG,
                 fg=MUTED_FG, font=("SF Pro Text", 10)).grid(row=0, column=0, sticky="w")
        ttk.Entry(pf, textvariable=self.src_var).grid(
            row=0, column=1, sticky="ew", padx=8, pady=3)
        ttk.Button(pf, text="Browse…",
                   command=lambda: self._browse(self.src_var)).grid(row=0, column=2)

        tk.Label(pf, text="Backup drive:", bg=DARK_BG,
                 fg=MUTED_FG, font=("SF Pro Text", 10)).grid(row=1, column=0, sticky="w")
        ttk.Entry(pf, textvariable=self.dst_var).grid(
            row=1, column=1, sticky="ew", padx=8, pady=3)
        ttk.Button(pf, text="Browse…",
                   command=lambda: self._browse(self.dst_var)).grid(row=1, column=2)

        # ── action buttons
        bf = tk.Frame(self, bg=DARK_BG)
        bf.pack(pady=8)

        self._scan_btn   = ttk.Button(bf, text="1  Scan & Compare", style="Scan.TButton",
                                      command=self._scan)
        self._sync_btn   = ttk.Button(bf, text="2  Sync to Backup",  style="Sync.TButton",
                                      command=self._sync)
        self._verify_btn = ttk.Button(bf, text="3  Full Verify",      style="Verify.TButton",
                                      command=self._verify)
        self._cancel_btn = ttk.Button(bf, text="✕  Cancel",           style="Cancel.TButton",
                                      command=self._request_cancel, state="disabled")

        self._scan_btn.pack(side="left", padx=5)
        self._sync_btn.pack(side="left", padx=5)
        self._verify_btn.pack(side="left", padx=5)
        self._cancel_btn.pack(side="left", padx=5)

        # ── progress bar
        pbar_frame = tk.Frame(self, bg=DARK_BG)
        pbar_frame.pack(fill="x", padx=14, pady=(6, 0))
        self.pbar_var = tk.DoubleVar()
        self.pbar = ttk.Progressbar(pbar_frame, variable=self.pbar_var,
                                    maximum=100, style="TProgressbar")
        self.pbar.pack(fill="x")

        # ── progress detail (file counter)
        detail_frame = tk.Frame(self, bg=DARK_BG)
        detail_frame.pack(fill="x", padx=14, pady=(2, 0))
        self.progress_var = tk.StringVar(value="")
        tk.Label(detail_frame, textvariable=self.progress_var,
                 bg=DARK_BG, fg=PURPLE, font=("Menlo", 10),
                 anchor="w").pack(side="left")

        # ── status line
        self.status_var = tk.StringVar(value="Ready — select source and backup drives, then click Scan & Compare.")
        tk.Label(self, textvariable=self.status_var,
                 bg=DARK_BG, fg=MUTED_FG, font=("SF Pro Text", 10),
                 anchor="w").pack(fill="x", padx=14, pady=(1, 0))

        # ── summary cards
        cf = tk.Frame(self, bg=DARK_BG)
        cf.pack(fill="x", padx=14, pady=8)
        cf.columnconfigure((0, 1, 2, 3), weight=1, uniform="card")

        self.card_vars: Dict[str, tk.StringVar] = {}
        cards = [
            ("identical", "✓  Identical",        GREEN,  "Perfect copies"),
            ("missing",   "→  Missing on backup", ORANGE, "Need to copy"),
            ("changed",   "!  Content differs",   RED,    "Hash mismatch"),
            ("extra",     "←  Only on backup",    PURPLE, "Not in source"),
        ]
        for col, (key, label, color, sub) in enumerate(cards):
            f = tk.Frame(cf, bg=SURFACE, padx=10, pady=8)
            f.grid(row=0, column=col, sticky="nsew", padx=4)
            tk.Label(f, text=label, bg=SURFACE, fg=color,
                     font=("SF Pro Text", 10, "bold")).pack(anchor="w")
            v = tk.StringVar(value="—")
            self.card_vars[key] = v
            tk.Label(f, textvariable=v, bg=SURFACE, fg=TEXT_FG,
                     font=("SF Pro Display", 26, "bold")).pack(anchor="w")
            tk.Label(f, text=sub, bg=SURFACE, fg=MUTED_FG,
                     font=("SF Pro Text", 9)).pack(anchor="w")

        # ── log
        lf = tk.Frame(self, bg=DARK_BG)
        lf.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        tk.Label(lf, text="Log", bg=DARK_BG, fg=MUTED_FG,
                 font=("SF Pro Text", 10, "bold")).pack(anchor="w")
        self.log = scrolledtext.ScrolledText(
            lf, height=14, font=FONT_MONO,
            bg=PANEL_BG, fg=TEXT_FG,
            insertbackground=TEXT_FG,
            selectbackground=SURFACE,
            relief="flat", bd=0,
            wrap="none"
        )
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        # colour tags
        self.log.tag_config("ok",      foreground=GREEN)
        self.log.tag_config("warn",    foreground=ORANGE)
        self.log.tag_config("err",     foreground=RED)
        self.log.tag_config("info",    foreground=PURPLE)
        self.log.tag_config("muted",   foreground=MUTED_FG)
        self.log.tag_config("heading", foreground=YELLOW, font=("Menlo", 10, "bold"))

    # ── helpers ─────────────────────────────────────────────────────────────

    def _browse(self, var: tk.StringVar):
        path = filedialog.askdirectory(title="Select folder or drive")
        if path:
            var.set(path)

    def _log(self, msg: str, tag: str = ""):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _set_status(self, msg: str):
        self.status_var.set(msg)
        self.update_idletasks()

    def _set_progress_detail(self, msg: str):
        self.progress_var.set(msg)
        self.update_idletasks()

    def _update_cards(self, identical, missing, changed, extra):
        self.card_vars["identical"].set(str(len(identical)))
        self.card_vars["missing"].set(str(len(missing)))
        self.card_vars["changed"].set(str(len(changed)))
        self.card_vars["extra"].set(str(len(extra)))

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        cancel_state = "normal" if busy else "disabled"
        self._scan_btn.configure(state=state)
        self._sync_btn.configure(state=state)
        self._verify_btn.configure(state=state)
        self._cancel_btn.configure(state=cancel_state)
        if not busy:
            self._set_progress_detail("")

    def _request_cancel(self):
        self._cancel.set()
        self._cancel_btn.configure(state="disabled")
        self._set_status("Cancelling — finishing current file…")

    def _guard(self):
        if self._busy:
            messagebox.showwarning("Busy", "An operation is already running.")
            return False
        return True

    def _paths(self):
        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()
        if not src or not dst:
            messagebox.showwarning("Missing paths",
                                   "Select both source and backup drives first.")
            return None, None
        if not os.path.isdir(src):
            messagebox.showerror("Not found", f"Source path not found:\n{src}")
            return None, None
        if not os.path.isdir(dst):
            messagebox.showerror("Not found", f"Backup path not found:\n{dst}")
            return None, None
        return src, dst

    def _indet(self, start: bool):
        if start:
            self.pbar.configure(style="Indet.TProgressbar", mode="indeterminate")
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.configure(style="TProgressbar", mode="determinate")
            self.pbar_var.set(0)

    # ── step 1: scan & compare ───────────────────────────────────────────────

    def _scan(self):
        if not self._guard():
            return
        src, dst = self._paths()
        if not src:
            return
        self._cancel.clear()
        self._set_busy(True)
        self._clear_log()
        self._indet(True)
        threading.Thread(target=self._do_scan, args=(src, dst), daemon=True).start()

    def _do_scan(self, src: str, dst: str):
        try:
            self.after(0, self._log, f"Scanning SOURCE: {src}", "heading")
            t0 = time.time()

            def on_src(rel, n):
                if n % 10 == 0:
                    self.after(0, self._set_progress_detail,
                               f"Source  {n:,} files hashed…  {rel[:60]}")

            self.src_map = scan_dir(Path(src), on_src, self._cancel)

            if self._cancel.is_set():
                self.after(0, self._finish_cancelled)
                return

            elapsed = time.time() - t0
            self.after(0, self._log,
                       f"  {len(self.src_map):,} files in {elapsed:.1f}s", "muted")

            self.after(0, self._log, f"\nScanning BACKUP: {dst}", "heading")
            t1 = time.time()

            def on_dst(rel, n):
                if n % 10 == 0:
                    self.after(0, self._set_progress_detail,
                               f"Backup  {n:,} files hashed…  {rel[:60]}")

            self.dst_map = scan_dir(Path(dst), on_dst, self._cancel)

            if self._cancel.is_set():
                self.after(0, self._finish_cancelled)
                return

            elapsed = time.time() - t1
            self.after(0, self._log,
                       f"  {len(self.dst_map):,} files in {elapsed:.1f}s", "muted")

            self._report_compare()
        finally:
            if not self._cancel.is_set():
                self.after(0, self._set_busy, False)
                self.after(0, self._indet, False)

    def _finish_cancelled(self):
        self._indet(False)
        self._set_busy(False)
        self._set_status("Cancelled.")
        self._set_progress_detail("")
        self._log("— Operation cancelled —", "warn")

    def _report_compare(self):
        identical, changed, missing, extra, errors = compare_maps(
            self.src_map, self.dst_map)

        self.after(0, self._update_cards, identical, missing, changed, extra)

        def emit():
            self._log("")
            self._log("─" * 58, "muted")
            self._log("  COMPARISON RESULTS", "heading")
            self._log("─" * 58, "muted")
            self._log(f"  ✓ Identical on both    {len(identical):>8,}", "ok")
            self._log(f"  → Missing on backup    {len(missing):>8,}",
                      "warn" if missing else "ok")
            self._log(f"  ! Content differs      {len(changed):>8,}",
                      "err" if changed else "ok")
            self._log(f"  ← Only on backup       {len(extra):>8,}", "info")
            if errors:
                self._log(f"  ⚠ Read errors          {len(errors):>8,}", "err")
            self._log("─" * 58, "muted")

            if missing:
                self._log(f"\nMISSING from backup ({len(missing):,} files):", "warn")
                for f in sorted(missing)[:200]:
                    self._log(f"  → {f}", "warn")
                if len(missing) > 200:
                    self._log(f"  … {len(missing)-200:,} more not shown", "muted")

            if changed:
                self._log(f"\nCONTENT MISMATCH ({len(changed):,} files):", "err")
                for f in sorted(changed)[:200]:
                    sh, dh = changed[f]
                    self._log(f"  ! {f}", "err")
                    self._log(f"      src: {sh or 'READ ERROR'}", "muted")
                    self._log(f"      bak: {dh or 'READ ERROR'}", "muted")
                if len(changed) > 200:
                    self._log(f"  … {len(changed)-200:,} more not shown", "muted")

            if not missing and not changed:
                self._log("")
                self._log("  PERFECT MIRROR — backup is 100% identical to source.", "ok")
                self._log("  Every file verified with SHA-256.", "ok")

            status = (
                "Backup is a perfect mirror!"
                if not missing and not changed
                else f"{len(missing):,} missing, {len(changed):,} differ — run Sync to Backup."
            )
            self._set_status(status)
            self._set_busy(False)
            self._indet(False)

        self.after(0, emit)

    # ── step 2: sync ─────────────────────────────────────────────────────────

    def _sync(self):
        if not self._guard():
            return
        if not self.src_map:
            messagebox.showwarning("Scan first",
                                   "Run Scan & Compare first so we know what to copy.")
            return
        src, dst = self._paths()
        if not src:
            return

        _, changed, missing, _, _ = compare_maps(self.src_map, self.dst_map)
        to_copy = sorted(missing) + sorted(changed)

        if not to_copy:
            messagebox.showinfo("Nothing to do",
                                "Backup is already a perfect mirror — nothing to copy!")
            return

        msg = (f"About to copy {len(to_copy):,} file(s) to backup:\n\n"
               f"  • {len(missing):,} missing\n"
               f"  • {len(changed):,} with different content\n\n"
               "Proceed?")
        if not messagebox.askyesno("Confirm sync", msg):
            return

        self._cancel.clear()
        self._set_busy(True)
        self._indet(False)
        self.pbar_var.set(0)
        threading.Thread(target=self._do_sync,
                         args=(src, dst, to_copy), daemon=True).start()

    def _do_sync(self, src: str, dst: str, to_copy: list):
        try:
            self._log("")
            self._log(f"SYNCING {len(to_copy):,} files to backup…", "heading")
            total = len(to_copy)
            ok = err = 0
            w = len(str(total))

            for i, rel in enumerate(to_copy, 1):
                if self._cancel.is_set():
                    self.after(0, self._log,
                               f"\n— Cancelled after {i-1}/{total} files ({ok} copied, {err} errors) —",
                               "warn")
                    self.after(0, self._set_status,
                               f"Cancelled. {ok} copied, {err} errors.")
                    return

                src_path = Path(src) / rel
                dst_path = Path(dst) / rel
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(src_path, dst_path)
                    self.after(0, self._log, f"  [{i:{w}}/{total}]  {rel}", "ok")
                    ok += 1
                except Exception as e:
                    self.after(0, self._log,
                               f"  [{i:{w}}/{total}]  ERROR {rel}: {e}", "err")
                    err += 1

                pct = i / total * 100
                self.after(0, self.pbar_var.set, pct)
                self.after(0, self._set_progress_detail,
                           f"{i:,} / {total:,} files  ({pct:.0f}%)  —  {ok} copied, {err} errors")
                if i % 20 == 0 or i == total:
                    self.after(0, self._set_status,
                               f"Copying… {i:,}/{total:,}  ({ok} ok, {err} errors)")

            self.after(0, self._log, "")
            if err == 0:
                self.after(0, self._log,
                           f"Sync complete — {ok:,} files copied with no errors.", "ok")
                self.after(0, self._log,
                           "Run 'Full Verify' to confirm 100% integrity.", "info")
                self.after(0, self._set_status,
                           "Sync done — click Full Verify for 100% confirmation.")
            else:
                self.after(0, self._log,
                           f"Sync finished with {err} error(s). Check log above.", "err")
                self.after(0, self._set_status,
                           f"Sync finished: {ok} copied, {err} errors.")
        finally:
            self.after(0, self._set_busy, False)

    # ── step 3: full verify ──────────────────────────────────────────────────

    def _verify(self):
        if not self._guard():
            return
        src, dst = self._paths()
        if not src:
            return
        self._cancel.clear()
        self._set_busy(True)
        self._clear_log()
        self._indet(True)
        threading.Thread(target=self._do_verify, args=(src, dst), daemon=True).start()

    def _do_verify(self, src: str, dst: str):
        try:
            self.after(0, self._log,
                       "FULL VERIFICATION — re-scanning both drives from scratch…", "heading")
            self.after(0, self._log,
                       "Every file's SHA-256 will be recomputed.", "muted")

            def on_src(rel, n):
                if n % 10 == 0:
                    self.after(0, self._set_progress_detail,
                               f"Source  {n:,} files verified…  {rel[:60]}")

            def on_dst(rel, n):
                if n % 10 == 0:
                    self.after(0, self._set_progress_detail,
                               f"Backup  {n:,} files verified…  {rel[:60]}")

            self.src_map = scan_dir(Path(src), on_src, self._cancel)
            if self._cancel.is_set():
                self.after(0, self._finish_cancelled)
                return

            self.dst_map = scan_dir(Path(dst), on_dst, self._cancel)
            if self._cancel.is_set():
                self.after(0, self._finish_cancelled)
                return

            self._report_compare()

            identical, changed, missing, extra, errors = compare_maps(
                self.src_map, self.dst_map)

            def finish():
                if not missing and not changed and not errors:
                    messagebox.showinfo(
                        "✅ 100% Verified",
                        f"Backup is a perfect mirror!\n\n"
                        f"{len(identical):,} files verified with SHA-256.\n"
                        f"Every byte matches — your photos are safe."
                    )
                else:
                    messagebox.showwarning(
                        "Verification failed",
                        f"{len(missing):,} files missing\n"
                        f"{len(changed):,} files have mismatched content\n\n"
                        "Run Sync to Backup, then Verify again."
                    )

            self.after(0, finish)
        finally:
            if not self._cancel.is_set():
                self.after(0, self._indet, False)


# ─── entry ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = PhotoVerifier()
    app.mainloop()
