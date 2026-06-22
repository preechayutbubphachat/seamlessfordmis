"""
SeamlessFordMIS GUI Launcher
============================
GUI wrapper สำหรับ offline/*.bat scripts บน Windows
ใช้ Python 3.10+ + CustomTkinter

วิธีใช้งาน:
  python seamlessfordmis_launcher.py           # จาก launcher/ directory
  SeamlessFordMIS-Launcher.exe                 # หลัง PyInstaller build

Working directory ต้องเป็น install root (C:\\SeamlessFordMIS\\app)
ตัว launcher จะหา root จาก sys.executable location หรือ __file__

ความปลอดภัย:
  - ไม่แสดง password จาก .env ในทุกกรณี
  - ไม่ upload ข้อมูลใดออกอินเทอร์เน็ต
  - ทุก action รันผ่าน offline/*.bat ที่มีอยู่แล้ว
  - require typed confirmation ก่อน restore (ส่งผ่านไปที่ restore.bat)
"""

import sys
import os
import subprocess
import threading
import time
import re
import shutil
from pathlib import Path
from datetime import datetime

import customtkinter as ctk

# ---------------------------------------------------------------------------
# ตรวจหา install root
# ---------------------------------------------------------------------------

def find_install_root() -> Path:
    """
    หา install root จาก:
    1. sys.executable location (กรณี PyInstaller .exe ใน {app}\\)
    2. __file__ location (กรณีรัน launcher/ source)
    3. CWD fallback
    """
    if getattr(sys, "frozen", False):
        # PyInstaller: exe อยู่ใน {app}\  หรือ  {app}\launcher\
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "docker-compose.yml").exists():
            return exe_dir
        parent = exe_dir.parent
        if (parent / "docker-compose.yml").exists():
            return parent
    else:
        # dev mode: script อยู่ใน launcher/
        script_dir = Path(__file__).parent
        parent = script_dir.parent
        if (parent / "docker-compose.yml").exists():
            return parent
        if (script_dir / "docker-compose.yml").exists():
            return script_dir

    cwd = Path.cwd()
    if (cwd / "docker-compose.yml").exists():
        return cwd

    return cwd


INSTALL_ROOT = find_install_root()
OFFLINE_DIR  = INSTALL_ROOT / "offline"
ENV_FILE     = INSTALL_ROOT / ".env"

# ---------------------------------------------------------------------------
# ตรวจสอบ HTTP_PORT จาก .env
# ---------------------------------------------------------------------------

def read_http_port() -> int:
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("HTTP_PORT=") and not line.startswith("#"):
                    val = line.split("=", 1)[1].strip()
                    if val.isdigit():
                        return int(val)
        except Exception:
            pass
    return 80


# ---------------------------------------------------------------------------
# สีและ theme
# ---------------------------------------------------------------------------

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

COLOR_GREEN  = "#22c55e"
COLOR_YELLOW = "#eab308"
COLOR_RED    = "#ef4444"
COLOR_GRAY   = "#6b7280"

STATUS_ICONS = {
    "ok":      "🟢",
    "warn":    "🟡",
    "error":   "🔴",
    "unknown": "⚪",
}


# ---------------------------------------------------------------------------
# ฟังก์ชัน scrub secrets จาก log output
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    # POSTGRES_PASSWORD=xxx  หรือ  DATABASE_URL=...password...
    re.compile(r"(POSTGRES_PASSWORD\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(DATABASE_URL\s*=\s*postgresql[^:]*://[^:]*:)[^@]+(@)", re.IGNORECASE),
    re.compile(r"(password\s*=\s*)\S+", re.IGNORECASE),
    re.compile(r"(CHANGE_ME_OFFLINE_DB_PASSWORD)", re.IGNORECASE),
]


def scrub_secrets(text: str) -> str:
    """ซ่อน password จาก output ก่อนแสดงในหน้าจอ"""
    for pat in _SECRET_PATTERNS:
        if pat.groups == 1:
            text = pat.sub(r"\1[HIDDEN]", text)
        elif pat.groups == 2:
            text = pat.sub(r"\1[HIDDEN]\2", text)
        else:
            text = pat.sub("[HIDDEN]", text)
    return text


# ---------------------------------------------------------------------------
# รัน .bat script
# ---------------------------------------------------------------------------

def run_bat(script_name: str, args: list[str] | None = None) -> subprocess.Popen:
    """
    รัน offline\\<script_name>.bat แบบ non-blocking
    คืน Popen object
    """
    bat_path = OFFLINE_DIR / script_name
    if not bat_path.exists():
        raise FileNotFoundError(f"ไม่พบ script: {bat_path}")

    cmd = ["cmd", "/c", str(bat_path)] + (args or [])
    return subprocess.Popen(
        cmd,
        cwd=str(INSTALL_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


# ---------------------------------------------------------------------------
# Health Check แบบ read-only
# ---------------------------------------------------------------------------

class HealthStatus:
    def __init__(self):
        self.docker: str   = "unknown"  # ok | error | unknown
        self.db: str       = "unknown"
        self.backend: str  = "unknown"
        self.frontend: str = "unknown"
        self.nginx: str    = "unknown"
        self.url: str      = ""
        self.lan_url: str  = ""
        self.last_check: str = ""

    def overall(self) -> str:
        statuses = [self.docker, self.db, self.backend, self.frontend, self.nginx]
        if any(s == "error" for s in statuses):
            return "error"
        if any(s == "unknown" for s in statuses):
            return "unknown"
        return "ok"


def check_health_background(callback):
    """รัน health check ใน background thread แล้วเรียก callback(HealthStatus)"""
    def _check():
        status = HealthStatus()
        port = read_http_port()
        status.url = f"http://localhost" if port == 80 else f"http://localhost:{port}"
        status.lan_url = first_lan_url(port)
        status.last_check = datetime.now().strftime("%H:%M:%S")

        # 1. Docker Engine
        try:
            r = subprocess.run(
                ["docker", "info"],
                capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW
            )
            status.docker = "ok" if r.returncode == 0 else "error"
        except Exception:
            status.docker = "error"

        if status.docker == "error":
            callback(status)
            return

        # 2. Container health via `docker compose ps`
        try:
            r = subprocess.run(
                ["docker", "compose", "ps", "--format", "{{.Name}}\t{{.Status}}"],
                cwd=str(INSTALL_ROOT),
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = r.stdout.lower()
            def svc_status(keywords: list[str]) -> str:
                """
                ตรวจสถานะ service จาก docker compose ps output
                Container names: seamlessfordmis-db, seamlessfordmis-backend, etc.
                """
                for line in output.splitlines():
                    if any(k in line for k in keywords):
                        if "healthy" in line:
                            return "ok"
                        if "running" in line:
                            return "warn"
                        if "exit" in line or "dead" in line or "error" in line:
                            return "error"
                return "unknown"

            # Container names ใน docker-compose.yml:
            #   seamlessfordmis-db, seamlessfordmis-backend,
            #   seamlessfordmis-frontend, seamlessfordmis-nginx
            status.db       = svc_status(["seamlessfordmis-db"])
            status.backend  = svc_status(["seamlessfordmis-backend"])
            status.frontend = svc_status(["seamlessfordmis-frontend"])
            status.nginx    = svc_status(["seamlessfordmis-nginx"])
        except Exception:
            pass

        # 3. HTTP smoke test
        if status.nginx == "ok":
            try:
                import requests as req
                r = req.get(f"{status.url}/health", timeout=5)
                if r.status_code != 200:
                    status.backend = "warn"
            except Exception:
                status.backend = "warn"

        callback(status)

    threading.Thread(target=_check, daemon=True).start()


def first_lan_url(port: int) -> str:
    """
    Return the first non-loopback IPv4 URL visible from ipconfig.
    Uses local OS output only; no internet/network probe.
    """
    try:
        r = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in r.stdout.splitlines():
            if "IPv4" not in line or ":" not in line:
                continue
            ip = line.split(":", 1)[1].strip()
            if ip and ip != "127.0.0.1" and not ip.startswith("169.254."):
                return f"http://{ip}" if port == 80 else f"http://{ip}:{port}"
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Main App Window
# ---------------------------------------------------------------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SeamlessFordMIS — Launcher")
        self.geometry("780x680")
        self.minsize(700, 580)
        self.resizable(True, True)

        # state
        self._running_proc: subprocess.Popen | None = None
        self._buttons_locked = False
        self._health = HealthStatus()

        self._build_ui()
        self._refresh_health()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # log panel expands

        # ---- Header ----
        header = ctk.CTkFrame(self, corner_radius=0, fg_color=("#1e40af", "#1e3a8a"))
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="🏥  SeamlessFordMIS",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        ctk.CTkLabel(
            header,
            text="ระบบคัดกรอง/ติดตามกลุ่มเป้าหมายแบบ Offline/LAN",
            font=ctk.CTkFont(size=12),
            text_color="#dbeafe",
        ).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        badge_frame = ctk.CTkFrame(header, fg_color=("#1d4ed8", "#1e40af"), corner_radius=6)
        badge_frame.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="w")
        ctk.CTkLabel(
            badge_frame,
            text="🔒  Local / ภายในหน่วยงาน — ข้อมูลไม่ออกนอกเครือข่าย",
            font=ctk.CTkFont(size=11),
            text_color="#93c5fd",
        ).pack(padx=8, pady=3)

        # ---- Status Area ----
        status_outer = ctk.CTkFrame(self, corner_radius=8)
        status_outer.grid(row=1, column=0, padx=12, pady=(8, 4), sticky="ew")
        status_outer.grid_columnconfigure((0,1,2,3,4,5), weight=1)

        self._status_labels: dict[str, ctk.CTkLabel] = {}
        items = [
            ("docker",   "Docker"),
            ("db",       "ฐานข้อมูล"),
            ("backend",  "Backend"),
            ("frontend", "Frontend"),
            ("nginx",    "nginx"),
            ("url",      "เว็บ"),
        ]
        for col, (key, label) in enumerate(items):
            frame = ctk.CTkFrame(status_outer, fg_color="transparent")
            frame.grid(row=0, column=col, padx=6, pady=8, sticky="nsew")
            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=10), text_color="gray").pack()
            lbl = ctk.CTkLabel(frame, text="⚪ —", font=ctk.CTkFont(size=11))
            lbl.pack()
            self._status_labels[key] = lbl

        # refresh button
        self._btn_refresh = ctk.CTkButton(
            status_outer, text="🔄 ตรวจสอบ", width=90, height=28,
            command=self._refresh_health, font=ctk.CTkFont(size=11),
        )
        self._btn_refresh.grid(row=0, column=6, padx=8, pady=8)
        self._last_check_lbl = ctk.CTkLabel(status_outer, text="", font=ctk.CTkFont(size=9), text_color="gray")
        self._last_check_lbl.grid(row=1, column=0, columnspan=7, pady=(0,4))

        self._url_detail_lbl = ctk.CTkLabel(status_outer, text="", font=ctk.CTkFont(size=10), text_color="gray")
        self._url_detail_lbl.grid(row=2, column=0, columnspan=7, pady=(0,6), sticky="w", padx=12)

        # ---- Action Buttons ----
        btn_frame = ctk.CTkScrollableFrame(self, label_text="", height=200)
        btn_frame.grid(row=2, column=0, padx=12, pady=4, sticky="nsew")
        self.grid_rowconfigure(2, weight=0)
        btn_frame.grid_columnconfigure((0,1,2,3), weight=1)

        self._action_buttons: list[ctk.CTkButton] = []

        actions = [
            # (label, command, color, row, col)
            ("▶  เริ่มระบบ",         self._start,        "#16a34a", 0, 0),
            ("⏹  หยุดระบบ",          self._stop,         "#dc2626", 0, 1),
            ("🔄  รีสตาร์ท",         self._restart,      "#2563eb", 0, 2),
            ("🌐  เปิดเว็บ",          self._open_web,     "#0891b2", 0, 3),
            ("📋  สถานะระบบ",        self._status,       "#6d28d9", 1, 0),
            ("📜  ดู Logs",           self._logs,         "#475569", 1, 1),
            ("💾  สำรองข้อมูล",       self._backup,       "#b45309", 1, 2),
            ("🔁  กู้คืนข้อมูล",      self._restore,      "#b91c1c", 1, 3),
            ("🗄️  รัน Migration",     self._migrate,      "#7c3aed", 2, 0),
            ("📦  โหลด Images",       self._load_images,  "#0f766e", 2, 1),
            ("📡  IP สำหรับ LAN",     self._show_lan_ip,  "#1d4ed8", 2, 2),
            ("🔍  ตรวจสอบระบบ",      self._healthcheck,  "#065f46", 2, 3),
            ("📖  เปิดคู่มือ",         self._open_guide,   "#334155", 3, 0),
        ]

        for label, cmd, color, row, col in actions:
            btn = ctk.CTkButton(
                btn_frame,
                text=label,
                command=cmd,
                fg_color=color,
                hover_color=color,
                height=44,
                font=ctk.CTkFont(size=12, weight="bold"),
                corner_radius=8,
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            self._action_buttons.append(btn)

        # ---- Warning Area ----
        self._warning_lbl = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#f59e0b",
            wraplength=720,
        )
        self._warning_lbl.grid(row=3, column=0, padx=12, pady=2, sticky="ew")

        # ---- Log Output Panel ----
        log_frame = ctk.CTkFrame(self, corner_radius=8)
        log_frame.grid(row=4, column=0, padx=12, pady=(4, 10), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))
        log_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            log_header, text="📋 Log Output", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            log_header, text="ล้าง", width=60, height=24,
            font=ctk.CTkFont(size=10),
            command=self._clear_log,
        ).grid(row=0, column=1)
        ctk.CTkButton(
            log_header, text="คัดลอก", width=70, height=24,
            font=ctk.CTkFont(size=10),
            command=self._copy_log,
        ).grid(row=0, column=2, padx=(6, 0))

        ctk.CTkLabel(
            self,
            text=(
                "ข้อควรระวัง: Backup/Export อาจมีข้อมูลส่วนบุคคล, Restore กระทบข้อมูลปัจจุบัน, "
                "Docker Desktop ต้องเปิดก่อนใช้งาน, และไม่ควรเปิดระบบออก Internet ถ้าไม่จำเป็น"
            ),
            font=ctk.CTkFont(size=10),
            text_color="#64748b",
            wraplength=730,
        ).grid(row=5, column=0, padx=12, pady=(0, 10), sticky="ew")

        self._log_box = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=10),
            state="disabled",
            wrap="word",
        )
        self._log_box.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")

    # ------------------------------------------------------------------
    # Health Refresh
    # ------------------------------------------------------------------

    def _refresh_health(self):
        self._status_labels["docker"].configure(text="⚪ ตรวจสอบ...")
        self._btn_refresh.configure(state="disabled")
        check_health_background(self._on_health_result)

    def _on_health_result(self, status: HealthStatus):
        self._health = status
        self.after(0, self._update_status_ui, status)

    def _update_status_ui(self, status: HealthStatus):
        def fmt(state: str, label: str = "") -> str:
            icon = STATUS_ICONS.get(state, "⚪")
            return f"{icon} {label}" if label else icon

        self._status_labels["docker"].configure(
            text=fmt(status.docker, "พร้อม" if status.docker == "ok" else "ไม่พร้อม")
        )
        self._status_labels["db"].configure(
            text=fmt(status.db, "healthy" if status.db == "ok" else status.db)
        )
        self._status_labels["backend"].configure(
            text=fmt(status.backend, "healthy" if status.backend == "ok" else status.backend)
        )
        self._status_labels["frontend"].configure(
            text=fmt(status.frontend, "healthy" if status.frontend == "ok" else status.frontend)
        )
        self._status_labels["nginx"].configure(
            text=fmt(status.nginx, "healthy" if status.nginx == "ok" else status.nginx)
        )

        port = read_http_port()
        url_text = "http://localhost" if port == 80 else f"http://localhost:{port}"
        self._status_labels["url"].configure(text=f"🔗 {url_text}")
        lan_text = f"LAN: {status.lan_url}" if status.lan_url else "LAN: กดปุ่ม IP สำหรับ LAN เพื่อตรวจสอบ"
        self._url_detail_lbl.configure(text=f"Local: {url_text}  |  {lan_text}")

        self._last_check_lbl.configure(
            text=f"ตรวจสอบล่าสุด: {status.last_check}  |  root: {INSTALL_ROOT}"
        )
        self._btn_refresh.configure(state="normal")

        if not ENV_FILE.exists():
            self._set_warning(f"⚠️  ไม่พบไฟล์ .env ที่ {ENV_FILE} — รัน offline\\install.bat หรือ copy .env.offline.example เป็น .env")
        elif status.docker == "error":
            self._set_warning("⚠️  Docker ไม่ทำงาน — กรุณาเปิด Docker Desktop แล้วรอจนพร้อม จากนั้นกด [ตรวจสอบ]")
        elif status.overall() == "error":
            self._set_warning("⚠️  บางบริการไม่ทำงาน — กด [เริ่มระบบ] เพื่อเริ่มบริการ")
        else:
            self._set_warning("")

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _log(self, text: str):
        clean = scrub_secrets(text)
        self._log_box.configure(state="normal")
        self._log_box.insert("end", clean)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _log_line(self, text: str):
        self._log(text + "\n")

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _copy_log(self):
        text = self._log_box.get("1.0", "end")
        clean = scrub_secrets(text)
        self.clipboard_clear()
        self.clipboard_append(clean)
        self._set_warning("คัดลอก log แล้ว — password/secret ถูกซ่อนก่อนคัดลอก")

    def _set_warning(self, text: str):
        self._warning_lbl.configure(text=text)

    # ------------------------------------------------------------------
    # Button lock/unlock
    # ------------------------------------------------------------------

    def _lock_buttons(self):
        self._buttons_locked = True
        for btn in self._action_buttons:
            btn.configure(state="disabled")
        self._btn_refresh.configure(state="disabled")

    def _unlock_buttons(self):
        self._buttons_locked = False
        for btn in self._action_buttons:
            btn.configure(state="normal")
        self._btn_refresh.configure(state="normal")

    # ------------------------------------------------------------------
    # Generic .bat runner (non-blocking, streams output to log)
    # ------------------------------------------------------------------

    def _run_script(self, script: str, args: list[str] | None = None, label: str = ""):
        if self._buttons_locked:
            return

        self._lock_buttons()
        self._log_line(f"\n{'='*60}")
        self._log_line(f"[{datetime.now().strftime('%H:%M:%S')}]  {label or script}")
        self._log_line(f"  root: {INSTALL_ROOT}")
        self._log_line(f"{'='*60}")

        def _stream():
            try:
                proc = run_bat(script, args)
                for line in proc.stdout:
                    self.after(0, self._log, line)
                proc.wait()
                rc = proc.returncode
                self.after(0, self._log_line, f"\n[exit code: {rc}]")
                if rc == 0:
                    self.after(0, self._set_warning, "")
                else:
                    self.after(0, self._set_warning, f"⚠️  {label or script} ออกด้วย exit code {rc} — ดู Log ด้านล่าง")
            except FileNotFoundError as e:
                self.after(0, self._log_line, f"[ERROR] {e}")
                self.after(0, self._set_warning, f"⚠️  ไม่พบ script: {script}")
            finally:
                self.after(0, self._unlock_buttons)
                self.after(2000, self._refresh_health)

        threading.Thread(target=_stream, daemon=True).start()

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _start(self):
        self._run_script("start.bat", label="เริ่มระบบ")

    def _stop(self):
        self._run_script("stop.bat", label="หยุดระบบ")

    def _restart(self):
        self._run_script("restart.bat", label="รีสตาร์ทระบบ")

    def _open_web(self):
        self._run_script("open-web.bat", label="เปิดเว็บ")

    def _status(self):
        self._run_script("status.bat", label="ตรวจสถานะระบบ")

    def _logs(self):
        self._run_script("logs.bat", label="ดู Logs")

    def _backup(self):
        self._run_script("backup.bat", label="สำรองข้อมูล")

    def _restore(self):
        """
        Restore ต้องการ path backup และ typed confirmation "RESTORE"
        แสดง dialog เพื่อขอ backup path ก่อน จากนั้นให้ restore.bat จัดการ prompt
        NOTE: restore.bat จะถามผู้ใช้พิมพ์ "RESTORE" ผ่าน cmd window ที่เปิดแยก
        """
        if self._buttons_locked:
            return

        # Dialog ขอ backup path
        dialog = ctk.CTkInputDialog(
            text=(
                "ระบุ path ของ backup ที่ต้องการกู้คืน\n\n"
                "ตัวอย่าง:  data\\backups\\20260526-143000\n\n"
                "⚠️  คำเตือน: การดำเนินการนี้จะล้าง database เดิมก่อนนำ backup กลับมา\n"
                "กระบวนการยืนยันจะเกิดขึ้นในหน้าต่าง Command Prompt"
            ),
            title="กู้คืนข้อมูล",
        )
        backup_path = dialog.get_input()
        if not backup_path or not backup_path.strip():
            self._log_line("[ยกเลิก] ไม่ได้ระบุ backup path")
            return

        backup_path = backup_path.strip()
        # ตรวจว่า directory มีอยู่จริง
        full_path = INSTALL_ROOT / backup_path
        if not full_path.exists():
            self._set_warning(f"⚠️  ไม่พบ backup directory: {full_path}")
            self._log_line(f"[ERROR] ไม่พบ: {full_path}")
            return

        # เปิด cmd window แยกเพื่อให้ผู้ใช้พิมพ์ "RESTORE" ได้
        bat_path = OFFLINE_DIR / "restore.bat"
        if not bat_path.exists():
            self._log_line(f"[ERROR] ไม่พบ restore.bat")
            return

        self._log_line(f"\n[กู้คืน] เปิดหน้าต่างยืนยัน... path: {backup_path}")
        self._log_line("โปรดดำเนินการในหน้าต่าง Command Prompt ที่เปิดขึ้นมา")
        try:
            subprocess.Popen(
                ["cmd", "/k", str(bat_path), backup_path],
                cwd=str(INSTALL_ROOT),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception as e:
            self._log_line(f"[ERROR] {e}")

    def _migrate(self):
        self._run_script("migrate.bat", label="รัน Database Migration")

    def _load_images(self):
        self._run_script("load-images.bat", label="โหลด Docker Images จาก offline package")

    def _show_lan_ip(self):
        self._run_script("show-lan-ip.bat", label="แสดง IP สำหรับเครื่องอื่นใน LAN")

    def _healthcheck(self):
        self._run_script("healthcheck.bat", label="ตรวจสอบระบบ (health check)")

    def _open_guide(self):
        guide = INSTALL_ROOT / "OFFLINE_INSTALL.md"
        if not guide.exists():
            self._set_warning(f"⚠️  ไม่พบคู่มือ: {guide}")
            self._log_line(f"[ERROR] ไม่พบคู่มือ: {guide}")
            return
        self._log_line(f"\n[เปิดคู่มือ] {guide}")
        try:
            os.startfile(str(guide))
        except Exception as exc:
            editor = shutil.which("notepad")
            if editor:
                subprocess.Popen([editor, str(guide)], cwd=str(INSTALL_ROOT))
            else:
                self._log_line(f"[ERROR] เปิดคู่มือไม่ได้: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # ตรวจ root ก่อนเริ่ม
    if not (INSTALL_ROOT / "docker-compose.yml").exists():
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "SeamlessFordMIS Launcher",
            f"ไม่พบ docker-compose.yml ใน:\n{INSTALL_ROOT}\n\n"
            "กรุณาวาง SeamlessFordMIS-Launcher.exe ไว้ใน C:\\SeamlessFordMIS\\app\\"
        )
        sys.exit(1)

    app = App()
    app.mainloop()
