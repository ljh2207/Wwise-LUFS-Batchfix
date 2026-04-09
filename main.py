import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import threading
import os
import json

try:
    import soundfile as sf
    import pyloudnorm as pyln
    import numpy as np
    AUDIO_OK = True
    AUDIO_ERR = ""
except ImportError as e:
    AUDIO_OK = False
    AUDIO_ERR = str(e)

try:
    from waapi import WaapiClient, CannotConnectToWaapiException
    WAAPI_OK = True
    WAAPI_ERR = ""
except ImportError as e:
    WAAPI_OK = False
    WAAPI_ERR = str(e)

WAAPI_URL   = "ws://127.0.0.1:8080/waapi"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# ─── LUFS 측정 ──────────────────────────────────────────────────────────────

SHORT_FILE_THRESHOLD = 1.0  # 초 미만은 LUFS 대신 Peak/RMS 표시

def measure_file(path: str) -> dict:
    try:
        data, rate = sf.read(path, always_2d=True)
        channels = data.shape[1]
        duration = len(data) / rate
        short = duration < SHORT_FILE_THRESHOLD

        peak_linear = float(np.max(np.abs(data)))
        peak_db = 20 * np.log10(peak_linear) if peak_linear > 0 else -96.0

        rms_linear = float(np.sqrt(np.mean(data ** 2)))
        rms_db = 20 * np.log10(rms_linear) if rms_linear > 0 else -96.0

        if short:
            lufs = None
        else:
            meter = pyln.Meter(rate)
            meas_data = data[:, : min(channels, 2)]
            try:
                lufs = meter.integrated_loudness(meas_data)
            except Exception:
                lufs = None

        return {
            "lufs": lufs, "peak_db": peak_db, "rms_db": rms_db,
            "duration": duration, "channels": channels,
            "sample_rate": rate, "short": short, "error": None,
        }
    except Exception as e:
        return {
            "lufs": None, "peak_db": None, "rms_db": None,
            "duration": None, "channels": None,
            "sample_rate": None, "short": False, "error": str(e),
        }


# ─── WAAPI 조회 ─────────────────────────────────────────────────────────────

def fetch_sources() -> tuple:
    if not WAAPI_OK:
        return [], f"waapi-client 미설치:\n{WAAPI_ERR}"

    try:
        with WaapiClient(url=WAAPI_URL) as client:
            # 선택된 오브젝트를 sound:originalWavFilePath 포함해서 한 번에 조회
            sel = client.call(
                "ak.wwise.ui.getSelectedObjects", {},
                options={"return": ["id", "name", "type", "path",
                                    "sound:originalWavFilePath"]},
            )
            objects = (sel or {}).get("objects", [])

            if not objects:
                return [], (
                    "선택된 오브젝트가 없습니다.\n"
                    "Wwise에서 측정할 사운드를 먼저 선택해주세요."
                )

            sources = []
            for obj in objects:
                obj_name = obj["name"]
                obj_type = obj.get("type", "")
                wav_path = obj.get("sound:originalWavFilePath", "")

                if wav_path:
                    # Sound 오브젝트 — 경로 직접 사용
                    fname = os.path.basename(wav_path)
                    err = None if os.path.exists(wav_path) else "파일 없음"
                    sources.append({
                        "object_name": obj_name,
                        "object_id":   obj.get("id", ""),
                        "object_path": obj.get("path", ""),
                        "file_name": fname,
                        "file_path": wav_path,
                        "error": err,
                    })
                else:
                    # Sound가 아닌 컨테이너 — WAQL로 하위 Sound 재귀 탐색
                    obj_path = obj.get("path", "")
                    try:
                        res = client.call(
                            "ak.wwise.core.object.get",
                            {
                                "waql": (
                                    f'from object "{obj_path}" '
                                    f'select descendants '
                                    f'where type = "Sound"'
                                ),
                            },
                            options={"return": ["id", "name", "path",
                                                "sound:originalWavFilePath"]},
                        )
                        children = (res or {}).get("return", [])
                    except Exception as e:
                        sources.append({
                            "object_name": obj_name,
                            "object_id":   "",
                            "object_path": "",
                            "file_name": "(오류)",
                            "file_path": "",
                            "error": f"하위 탐색 실패: {e}",
                        })
                        continue

                    if not children:
                        sources.append({
                            "object_name": obj_name,
                            "object_id":   "",
                            "object_path": "",
                            "file_name": "(소스 없음)",
                            "file_path": "",
                            "error": f"하위 Sound 없음 (type: {obj_type})",
                        })
                        continue

                    for child in children:
                        child_wav = child.get("sound:originalWavFilePath", "")
                        if not child_wav:
                            continue
                        fname = os.path.basename(child_wav)
                        err = None if os.path.exists(child_wav) else "파일 없음"
                        sources.append({
                            "object_name": child.get("name", obj_name),
                            "object_id":   child.get("id", ""),
                            "object_path": child.get("path", ""),
                            "file_name": fname,
                            "file_path": child_wav,
                            "error": err,
                        })

        return sources, None

    except CannotConnectToWaapiException:
        return [], (
            "Wwise에 연결할 수 없습니다.\n"
            "Wwise가 실행 중인지, WAAPI가 활성화되어 있는지 확인하세요.\n"
            "(Project > User Preferences > Enable WAAPI)"
        )
    except Exception as e:
        return [], f"연결 오류: {e}"


# ─── 색상 헬퍼 ──────────────────────────────────────────────────────────────

def lufs_color(lufs):
    if lufs is None or lufs < -70:
        return "#9e9e9e"
    if lufs > -6:
        return "#ef5350"
    if lufs > -12:
        return "#ffa726"
    if lufs > -30:
        return "#66bb6a"
    return "#42a5f5"


def peak_color(peak_db):
    if peak_db is None:
        return "#9e9e9e"
    if peak_db > -1:
        return "#ef5350"
    if peak_db > -6:
        return "#ffa726"
    return "#66bb6a"


def fmt_lufs(v):
    if v is None:
        return "—"
    if v < -70:
        return "-∞"
    return f"{v:.1f}"


# ─── UI ─────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    BG        = "#2b2b2b"
    BG_HEADER = "#3c3c3c"
    BG_ROW    = "#333333"
    FG        = "#d4d4d4"
    FG_DIM    = "#8c8c8c"
    ACCENT    = "#e8a400"

    COLUMNS = ("✓", "오브젝트", "파일명", "Integrated LUFS", "Sample Peak", "Ch", "Duration")
    COL_W   = (28, 180, 200, 140, 120, 40, 80)

    def __init__(self):
        super().__init__()
        self.title("Wwise LUFS Meter")
        self.minsize(640, 420)
        self.configure(bg=self.BG)
        self._restore_geometry()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.rows_data:       list[dict] = []
        self._full_values:    dict[str, tuple] = {}
        self._checked:        dict[str, bool] = {}
        self._last_check_iid: str | None = None
        self._truncate_job = None
        self._build_style()
        self._build_ui()

    def _restore_geometry(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            self.geometry(cfg.get("geometry", "960x620"))
        except Exception:
            self.geometry("960x620")

    def _on_close(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump({"geometry": self.wm_geometry()}, f)
        except Exception:
            pass
        self.destroy()

    # ── 스타일 ──

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame",       background=self.BG)
        style.configure("TLabel",       background=self.BG,        foreground=self.FG,     font=("Segoe UI", 11))
        style.configure("Title.TLabel", background=self.BG,        foreground=self.FG,     font=("Segoe UI", 13, "bold"))
        style.configure("Dim.TLabel",   background=self.BG,        foreground=self.FG_DIM, font=("Segoe UI", 10))
        style.configure("Status.TLabel",background=self.BG,        foreground=self.FG_DIM, font=("Segoe UI", 10))

        style.configure("Measure.TButton",
            background=self.ACCENT, foreground="#1a1a1a",
            font=("Segoe UI", 11, "bold"), relief="flat", padding=(12, 4),
            borderwidth=0)
        style.map("Measure.TButton",
            background=[("active", "#f0b800"), ("disabled", "#4a4a4a")],
            foreground=[("disabled", "#6a6a6a")])

        style.configure("Copy.TButton",
            background=self.BG_HEADER, foreground=self.FG,
            font=("Segoe UI", 11), relief="flat", padding=(12, 4),
            borderwidth=0)
        style.map("Copy.TButton",
            background=[("active", "#4a4a4a"), ("disabled", "#2b2b2b")],
            foreground=[("disabled", "#5a5a5a")])

        style.configure("Normalize.TButton",
            background="#3a5a3a", foreground=self.FG,
            font=("Segoe UI", 11), relief="flat", padding=(12, 4),
            borderwidth=0)
        style.map("Normalize.TButton",
            background=[("active", "#4a7a4a"), ("disabled", "#2b2b2b")],
            foreground=[("disabled", "#5a5a5a")])

        SEP = "#555555"
        style.configure("Treeview",
            background=self.BG, fieldbackground=self.BG,
            foreground=self.FG, rowheight=26, font=("Segoe UI", 11),
            bordercolor=SEP, relief="flat", separatorwidth=1)
        style.configure("Treeview.Heading",
            background=self.BG_HEADER, foreground=self.FG_DIM,
            font=("Segoe UI", 10, "bold"), relief="groove",
            borderwidth=1, bordercolor=SEP, padding=(4, 4))
        style.map("Treeview",
            background=[("selected", "#4a4a4a")],
            foreground=[("selected", self.FG)])
        style.map("Treeview.Heading",
            background=[("active", "#484848")],
            foreground=[("active", self.FG)])

        style.configure("TScrollbar",
            background=self.BG_HEADER, troughcolor=self.BG,
            bordercolor=self.BG, arrowcolor=self.FG_DIM,
            relief="flat", borderwidth=0)
        style.map("TScrollbar",
            background=[("active", "#4a4a4a")])

        style.configure("TProgressbar",
            troughcolor=self.BG_HEADER, background=self.ACCENT, thickness=3)

    # ── UI 구성 ──

    def _build_ui(self):
        root_frame = ttk.Frame(self, padding=16)
        root_frame.pack(fill=tk.BOTH, expand=True)

        # 헤더
        header = ttk.Frame(root_frame)
        header.pack(fill=tk.X)

        left = ttk.Frame(header)
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(left, text="Wwise LUFS Meter", style="Title.TLabel").pack(anchor="w")

        legend_frame = ttk.Frame(left)
        legend_frame.pack(anchor="w", pady=(2, 0))
        ttk.Label(legend_frame, text="LUFS: ", style="Dim.TLabel").pack(side=tk.LEFT)
        for hex_col, label in [
            ("ef5350", "> −6  과도"),
            ("ffa726", "−6 ~ −12  높음"),
            ("66bb6a", "−12 ~ −30  적정"),
            ("42a5f5", "< −30  낮음"),
            ("ffcc02", "⚠ 1초 미만 (Peak/RMS)"),
        ]:
            dot = tk.Canvas(legend_frame, width=10, height=10,
                            bg=self.BG, highlightthickness=0)
            dot.pack(side=tk.LEFT, padx=(4, 2))
            dot.create_rectangle(0, 0, 10, 10, fill=f"#{hex_col}", outline="")
            ttk.Label(legend_frame, text=label, style="Dim.TLabel").pack(side=tk.LEFT, padx=(0, 6))

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side=tk.RIGHT, anchor="n")

        self.copy_btn = ttk.Button(btn_frame, text="TSV 복사", style="Copy.TButton",
                                   state="disabled", command=self._on_copy)
        self.copy_btn.pack(side=tk.LEFT, padx=(0, 12))

        # Target LUFS 입력
        ttk.Label(btn_frame, text="Target:", style="Dim.TLabel").pack(side=tk.LEFT)
        self.target_lufs_var = tk.StringVar(value="-14.0")
        self._target_spinbox = tk.Spinbox(
            btn_frame, textvariable=self.target_lufs_var,
            from_=-60.0, to=0.0, increment=0.5, width=6, format="%.1f",
            bg="#3c3c3c", fg=self.FG, insertbackground=self.FG,
            buttonbackground="#4a4a4a", relief="flat",
            font=("Segoe UI", 11), highlightthickness=0,
        )
        self._target_spinbox.pack(side=tk.LEFT, padx=(4, 2))
        ttk.Label(btn_frame, text="LUFS", style="Dim.TLabel").pack(side=tk.LEFT, padx=(0, 6))

        self.normalize_btn = ttk.Button(btn_frame, text="볼륨 적용",
                                        style="Normalize.TButton",
                                        state="disabled", command=self._on_normalize)
        self.normalize_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.measure_btn = ttk.Button(btn_frame, text="측정", style="Measure.TButton",
                                      command=self._on_measure)
        self.measure_btn.pack(side=tk.LEFT)

        # 구분선
        sep = tk.Frame(root_frame, height=1, bg=self.BG_HEADER)
        sep.pack(fill=tk.X, pady=(8, 4))

        # 진행 표시
        self.progress = ttk.Progressbar(root_frame, mode="indeterminate",
                                        style="TProgressbar")

        # 테이블
        table_frame = ttk.Frame(root_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.tree = ttk.Treeview(table_frame, columns=self.COLUMNS,
                                  show="headings", selectmode="extended")
        for col, w in zip(self.COLUMNS, self.COL_W):
            if col == "✓":
                self.tree.heading(col, text="✓", anchor="center",
                                  command=self._toggle_check_all)
                self.tree.column(col, width=w, anchor="center", minwidth=w, stretch=False)
            else:
                anchor = "e" if col in ("Integrated LUFS", "Sample Peak", "Ch", "Duration") else "w"
                self.tree.heading(col, text=col, anchor=anchor)
                self.tree.column(col, width=w, anchor=anchor, minwidth=40)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,   command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)

        def autoscroll(sbar, first, last):
            first, last = float(first), float(last)
            if first <= 0 and last >= 1:
                sbar.grid_remove()
            else:
                sbar.grid()
            sbar.set(first, last)

        self.tree.configure(
            yscrollcommand=lambda f, l: autoscroll(vsb, f, l),
            xscrollcommand=lambda f, l: autoscroll(hsb, f, l),
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self._cell_font = tkfont.Font(family="Segoe UI", size=11)
        self.tree.bind("<Configure>",      self._schedule_truncation)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        # 상태 바
        self.status_var = tk.StringVar(value="Wwise에서 사운드를 선택한 뒤 [측정] 버튼을 누르세요.")
        ttk.Label(root_frame, textvariable=self.status_var,
                  style="Status.TLabel").pack(anchor="w", pady=(6, 0))

    # ── Ellipsis 트런케이션 ──

    def _truncate(self, text: str, col_idx: int) -> str:
        col = self.COLUMNS[col_idx]
        available = self.tree.column(col, "width") - 12
        if available <= 0 or self._cell_font.measure(text) <= available:
            return text
        s = text
        while s and self._cell_font.measure(s + "…") > available:
            s = s[:-1]
        return (s + "…") if s else "…"

    def _schedule_truncation(self, *_):
        if self._truncate_job:
            self.after_cancel(self._truncate_job)
        self._truncate_job = self.after(80, self._refresh_truncation)

    def _refresh_truncation(self):
        self._truncate_job = None
        for iid, full_vals in self._full_values.items():
            try:
                truncated = tuple(
                    v if i == 0 else self._truncate(v, i)
                    for i, v in enumerate(full_vals)
                )
                self.tree.item(iid, values=truncated)
            except tk.TclError:
                pass

    # ── 체크박스 ──

    def _on_tree_click(self, event):
        self._schedule_truncation(event)
        region = self.tree.identify_region(event.x, event.y)
        col    = self.tree.identify_column(event.x)
        row    = self.tree.identify_row(event.y)
        if region != "cell" or col != "#1" or not row:
            return
        shift = bool(event.state & 0x0001)
        if shift and self._last_check_iid:
            # 마지막 체크 행 ~ 현재 행 범위를 일괄 토글
            all_iids = self.tree.get_children()
            try:
                a = all_iids.index(self._last_check_iid)
                b = all_iids.index(row)
            except ValueError:
                self._toggle_check(row)
                return
            lo, hi = min(a, b), max(a, b)
            target_state = self._checked.get(self._last_check_iid, False)
            for iid in all_iids[lo: hi + 1]:
                self._set_check(iid, target_state)
        else:
            self._toggle_check(row)

    def _set_check(self, iid: str, state: bool):
        self._checked[iid] = state
        char = "☑" if state else "☐"
        vals = list(self.tree.item(iid, "values"))
        vals[0] = char
        self.tree.item(iid, values=vals)
        full = list(self._full_values.get(iid, vals))
        full[0] = char
        self._full_values[iid] = tuple(full)

    def _toggle_check_all(self):
        all_iids = self.tree.get_children()
        if not all_iids:
            return
        # 모두 체크된 상태면 전체 해제, 아니면 전체 선택
        target = not all(self._checked.get(iid, False) for iid in all_iids)
        for iid in all_iids:
            self._set_check(iid, target)

    def _toggle_check(self, iid: str):
        self._set_check(iid, not self._checked.get(iid, False))
        self._last_check_iid = iid

    # ── 이벤트 핸들러 ──

    def _on_measure(self):
        self.rows_data = []
        self._full_values = {}
        self._checked = {}
        self._last_check_iid = None
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.measure_btn.configure(state="disabled")
        self.copy_btn.configure(state="disabled")
        self.progress.pack(fill=tk.X, before=self.tree.master)
        self.progress.start(10)
        self.status_var.set("Wwise 연결 중...")

        threading.Thread(target=self._run_measure, daemon=True).start()

    def _run_measure(self):
        if not AUDIO_OK:
            self.after(0, self._finish, [], f"오디오 라이브러리 오류: {AUDIO_ERR}")
            return

        sources, err = fetch_sources()
        if err:
            self.after(0, self._finish, [], err)
            return

        self.after(0, lambda: self.status_var.set(f"{len(sources)}개 파일 측정 중..."))

        results = []
        ok_count = 0
        err_count = 0

        for src in sources:
            if src["error"] or not src["file_path"]:
                meas = None
                err_count += 1
            else:
                meas = measure_file(src["file_path"])
                if meas["error"]:
                    err_count += 1
                else:
                    ok_count += 1

            results.append((src, meas))

        self.after(0, self._finish, results,
                   f"완료: {ok_count}개 측정됨" + (f", {err_count}개 오류" if err_count else ""))

    def _finish(self, results, msg):
        self.progress.stop()
        self.progress.pack_forget()

        short_count = 0

        for src, meas in results:
            obj   = src["object_name"]
            fname = src["file_name"]
            err   = src.get("error") or (meas.get("error") if meas else None)

            if err and (not meas or meas.get("peak_db") is None):
                full = ("☐", obj, fname, err, "—", "—", "—")
                iid = self.tree.insert("", "end", values=full)
                self.tree.tag_configure("err", foreground="#ef9a9a")
                self.tree.item(iid, tags=("err",))
                self._full_values[iid] = full
                self._checked[iid] = False
                self.rows_data.append({"object": obj, "file": fname,
                    "lufs": None, "rms": None, "peak": None,
                    "channels": None, "duration": None, "short": False,
                    "object_id": src.get("object_id", ""),
                    "object_path": src.get("object_path", ""),
                    "iid": iid})
                continue

            lufs  = meas["lufs"]     if meas else None
            peak  = meas["peak_db"]  if meas else None
            rms   = meas["rms_db"]   if meas else None
            ch    = meas["channels"] if meas else None
            dur   = meas["duration"] if meas else None
            short = meas.get("short", False) if meas else False

            peak_str = f"{peak:.1f} dBFS" if peak is not None else "—"
            dur_str  = f"{dur:.2f}s"      if dur  is not None else "—"
            ch_str   = str(ch) if ch else "—"

            if short:
                short_count += 1
                rms_str  = f"{rms:.1f} dB" if rms is not None else "—"
                lufs_str = f"⚠  RMS  {rms_str}"
                tag = "short"
                self.tree.tag_configure("short", foreground="#ffcc02")
            else:
                lufs_str = f"{fmt_lufs(lufs)} LUFS"
                tag = f"lufs_{lufs_color(lufs).lstrip('#')}"
                self.tree.tag_configure(tag, foreground=lufs_color(lufs))

            full = ("☐", obj, fname, lufs_str, peak_str, ch_str, dur_str)
            iid = self.tree.insert("", "end", values=full, tags=(tag,))
            self._full_values[iid] = full
            self._checked[iid] = False

            self.rows_data.append({"object": obj, "file": fname,
                "lufs": lufs, "rms": rms, "peak": peak,
                "channels": ch, "duration": dur, "short": short,
                "object_id": src.get("object_id", ""),
                "object_path": src.get("object_path", ""),
                "iid": iid})

        self.measure_btn.configure(state="normal")
        if any(r["peak"] is not None for r in self.rows_data):
            self.copy_btn.configure(state="normal")
        has_normalizable = any(
            r.get("lufs") is not None and r.get("object_id")
            for r in self.rows_data
        )
        if has_normalizable:
            self.normalize_btn.configure(state="normal")
        if short_count:
            msg += f"  |  ⚠ {short_count}개 1초 미만 (LUFS 생략, Peak/RMS 표시)"
        self.status_var.set(msg)
        self._refresh_truncation()

    def _on_normalize(self):
        try:
            target = float(self.target_lufs_var.get())
        except ValueError:
            self.status_var.set("Target LUFS 값이 유효하지 않습니다.")
            return
        if not (-60.0 <= target <= 0.0):
            self.status_var.set("Target LUFS는 -60.0 ~ 0.0 범위여야 합니다.")
            return

        checked_iids  = {iid for iid, v in self._checked.items() if v}
        selected_iids = set(self.tree.selection())
        if checked_iids:
            rows = [r for r in self.rows_data if r.get("iid") in checked_iids]
            scope_msg = f"체크된 {len(rows)}개"
        elif selected_iids:
            rows = [r for r in self.rows_data if r.get("iid") in selected_iids]
            scope_msg = f"선택된 {len(rows)}개"
        else:
            rows = list(self.rows_data)
            scope_msg = f"전체 {len(rows)}개"

        self.normalize_btn.configure(state="disabled")
        self.measure_btn.configure(state="disabled")
        self.status_var.set(f"Target {target:.1f} LUFS — {scope_msg} 볼륨 적용 중...")
        threading.Thread(target=self._run_normalize, args=(target, rows), daemon=True).start()

    def _run_normalize(self, target: float, rows: list):
        try:
            with WaapiClient(url=WAAPI_URL) as client:
                adjusted, skipped = 0, 0
                for r in rows:
                    if r.get("lufs") is None or not r.get("object_path"):
                        skipped += 1
                        continue

                    obj_path = r["object_path"]
                    # Volume = target - source_lufs (절대값 계산, 기존 Volume 무관)
                    new_vol  = max(-96.0, min(24.0, target - r["lufs"]))

                    client.call(
                        "ak.wwise.core.object.setProperty",
                        {
                            "object":   obj_path,
                            "property": "Volume",
                            "value":    new_vol,
                        },
                    )
                    adjusted += 1

            status_msg = f"볼륨 적용 완료: {adjusted}개 조정됨"
            if skipped:
                status_msg += f", {skipped}개 건너뜀 (1초 미만 또는 오류)"
            toast_msg = f"✓  볼륨 적용 완료  —  {adjusted}개 조정됨"
            self.after(0, lambda s=status_msg, t=toast_msg: (
                self.status_var.set(s), self._show_toast(t)))

        except CannotConnectToWaapiException:
            self.after(0, lambda: self.status_var.set(
                "Wwise 연결 실패 — WAAPI 활성화 확인"))
        except Exception as e:
            self.after(0, lambda m=str(e): self.status_var.set(f"볼륨 적용 오류: {m}"))
        finally:
            self.after(0, lambda: self.normalize_btn.configure(state="normal"))
            self.after(0, lambda: self.measure_btn.configure(state="normal"))

    def _show_toast(self, message: str):
        overlay = tk.Frame(self, bg="#1a1a1a")
        overlay.place(x=0, y=0, relwidth=1, relheight=1)

        toast = tk.Frame(overlay, bg="#3a6b3a", padx=24, pady=18)
        toast.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            toast, text=message,
            bg="#3a6b3a", fg="#ffffff",
            font=("Segoe UI", 16, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 24))
        tk.Button(
            toast, text="확인",
            bg="#2a5a2a", fg="#ffffff",
            font=("Segoe UI", 15), relief="flat",
            padx=15, pady=3, cursor="hand2",
            activebackground="#1e4a1e", activeforeground="#ffffff",
            command=overlay.destroy,
        ).pack(side=tk.LEFT)

    def _on_copy(self):
        lines = ["오브젝트\t파일명\tIntegrated LUFS\tRMS (dB)\tSample Peak (dBFS)\t채널\t길이(s)"]
        for r in self.rows_data:
            peak_str = f"{r['peak']:.1f}" if r["peak"] is not None else "—"
            rms_str  = f"{r['rms']:.1f}"  if r.get("rms") is not None else "—"
            dur_str  = f"{r['duration']:.2f}" if r["duration"] is not None else "—"
            lufs_str = f"⚠ 1초 미만" if r.get("short") else fmt_lufs(r["lufs"])
            lines.append(
                f"{r['object']}\t{r['file']}\t"
                f"{lufs_str}\t{rms_str}\t{peak_str}\t"
                f"{r['channels'] or '—'}\t{dur_str}"
            )
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.status_var.set("클립보드에 복사됨 — Excel/스프레드시트에 붙여넣기 가능")


if __name__ == "__main__":
    app = App()
    app.mainloop()
