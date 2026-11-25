import os
import sys
import time
import queue
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import cv2
import numpy as np
from PIL import Image, ImageTk
import customtkinter as ctk

import excel_manager
from attendance import AttendanceManager
from face_engine import FaceEngine

# Application Constants
APP_TITLE = "AttendIQ – Smart Facial Recognition Attendance"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 760
MIN_WIDTH = 1000
MIN_HEIGHT = 650

# Design System Colors
COLOR_BG_DARK = "#0F1117"          # Rich dark background
COLOR_SIDEBAR = "#161922"          # Dark slate sidebar
COLOR_CARD = "#1C202E"             # Card background
COLOR_CARD_HOVER = "#24293B"       # Card hover
COLOR_ACCENT = "#6366F1"           # Indigo / Electric violet
COLOR_ACCENT_HOVER = "#4F46E5"     # Darker Indigo
COLOR_SUCCESS = "#10B981"          # Emerald green
COLOR_WARNING = "#F59E0B"          # Amber / Orange
COLOR_DANGER = "#EF4444"           # Coral red
COLOR_TEXT_MAIN = "#F8FAFC"        # Off-white
COLOR_TEXT_MUTED = "#94A3B8"       # Light slate

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ToastNotification(ctk.CTkFrame):
    """Floating toast notification for real-time feedback."""
    def __init__(self, master, message: str, toast_type: str = "success", duration_ms: int = 4000):
        color_map = {
            "success": (COLOR_SUCCESS, "✔"),
            "warning": (COLOR_WARNING, "⚠"),
            "danger": (COLOR_DANGER, "✖"),
            "info": (COLOR_ACCENT, "ℹ")
        }
        accent, icon = color_map.get(toast_type, (COLOR_ACCENT, "ℹ"))

        super().__init__(
            master,
            fg_color=COLOR_CARD,
            border_color=accent,
            border_width=2,
            corner_radius=12
        )
        self.duration_ms = duration_ms

        icon_lbl = ctk.CTkLabel(
            self,
            text=icon,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=accent,
            width=28
        )
        icon_lbl.pack(side="left", padx=(14, 6), pady=10)

        msg_lbl = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="normal"),
            text_color=COLOR_TEXT_MAIN,
            wraplength=380,
            justify="left"
        )
        msg_lbl.pack(side="left", padx=(4, 16), pady=10)

        # Place toast at bottom right of master
        self.place(relx=0.98, rely=0.95, anchor="se")
        self.after(self.duration_ms, self.dismiss)

    def dismiss(self):
        try:
            self.destroy()
        except Exception:
            pass


class AttendIQApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.configure(fg_color=COLOR_BG_DARK)

        # Initialize Backend Subsystems
        excel_manager.init_excel_files()
        self.att_mgr = AttendanceManager()
        self.face_engine = FaceEngine(tolerance=self.att_mgr.settings.get("face_confidence_threshold", 0.50))

        # Active Camera Worker Reference
        self.active_camera_page = None

        # Set Window Icon
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                icon_img = ImageTk.PhotoImage(Image.open(logo_path))
                self.wm_iconphoto(True, icon_img)
            except Exception:
                pass

        # Build UI Scaffold
        self._build_sidebar()
        self._build_content_area()

        # Handle Clean Shutdown
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Default Page
        self.show_page("home")

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=0,
            fg_color=COLOR_SIDEBAR,
            border_width=0
        )
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        # App Brand Header
        header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header_frame.pack(fill="x", padx=16, pady=(20, 24))

        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                pil_logo = Image.open(logo_path).resize((42, 42), Image.Resampling.LANCZOS)
                self.logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(42, 42))
                logo_lbl = ctk.CTkLabel(header_frame, image=self.logo_img, text="")
                logo_lbl.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        app_lbl = ctk.CTkLabel(
            title_box,
            text="AttendIQ",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
            anchor="w"
        )
        app_lbl.pack(fill="x")

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="Facial Biometrics AI",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        sub_lbl.pack(fill="x")

        # Navigation Divider
        divider = ctk.CTkFrame(self.sidebar, height=1, fg_color="#262A38")
        divider.pack(fill="x", padx=16, pady=(0, 16))

        # Nav Buttons List
        self.nav_buttons = {}
        nav_items = [
            ("home", "  🏠   Home"),
            ("mark_attendance", "  📷   Mark Attendance"),
            ("register", "  👤+  Register Student"),
            ("students", "  👥   Students"),
            ("records", "  📊   Attendance Logs"),
            ("settings", "  ⚙️   Settings"),
        ]

        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="normal"),
                anchor="w",
                height=42,
                corner_radius=10,
                fg_color="transparent",
                text_color=COLOR_TEXT_MUTED,
                hover_color=COLOR_CARD_HOVER,
                command=lambda k=key: self.show_page(k)
            )
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[key] = btn

        # Bottom System Info Badge
        bottom_box = ctk.CTkFrame(self.sidebar, fg_color=COLOR_CARD, corner_radius=10)
        bottom_box.pack(side="bottom", fill="x", padx=12, pady=16)

        sys_dot = ctk.CTkLabel(bottom_box, text="●", text_color=COLOR_SUCCESS, font=ctk.CTkFont(size=14))
        sys_dot.pack(side="left", padx=(10, 4), pady=8)

        sys_lbl = ctk.CTkLabel(
            bottom_box,
            text="Offline • Excel Engine",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLOR_TEXT_MUTED
        )
        sys_lbl.pack(side="left", padx=(0, 10), pady=8)

    def _build_content_area(self):
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        # Create pages
        self.pages = {
            "home": HomePage(self.content_container, self),
            "mark_attendance": MarkAttendancePage(self.content_container, self),
            "register": RegisterStudentPage(self.content_container, self),
            "students": StudentsPage(self.content_container, self),
            "records": AttendanceRecordsPage(self.content_container, self),
            "settings": SettingsPage(self.content_container, self)
        }

    def show_page(self, page_name: str):
        # Stop any active camera from previous page before switching
        if self.active_camera_page and self.active_camera_page != self.pages.get(page_name):
            self.active_camera_page.stop_camera()
            self.active_camera_page = None

        # Update Navigation Button Styles
        for key, btn in self.nav_buttons.items():
            if key == page_name:
                btn.configure(fg_color=COLOR_ACCENT, text_color=COLOR_TEXT_MAIN, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(family="Segoe UI", size=13, weight="normal"))

        # Hide all pages and show requested page
        for p in self.pages.values():
            p.pack_forget()

        target_page = self.pages[page_name]
        target_page.pack(fill="both", expand=True)
        if hasattr(target_page, "on_enter"):
            target_page.on_enter()

    def toast(self, message: str, toast_type: str = "success"):
        """Displays floating toast notification."""
        ToastNotification(self, message=message, toast_type=toast_type)

    def on_close(self):
        """Releases camera and exits cleanly."""
        if self.active_camera_page:
            try:
                self.active_camera_page.stop_camera()
            except Exception:
                pass
        self.destroy()


# ==============================================================================
# 1. HOME PAGE
# ==============================================================================
class HomePage(ctk.CTkFrame):
    def __init__(self, master, app: AttendIQApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build_ui()
        self._start_clock()

    def _build_ui(self):
        # Header Row
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 20))

        welcome_box = ctk.CTkFrame(top_row, fg_color="transparent")
        welcome_box.pack(side="left", fill="both")

        lbl_greeting = ctk.CTkLabel(
            welcome_box,
            text="Welcome to AttendIQ",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
            anchor="w"
        )
        lbl_greeting.pack(fill="x")

        self.lbl_clock = ctk.CTkLabel(
            welcome_box,
            text="Loading time...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.lbl_clock.pack(fill="x", pady=(2, 0))

        # Quick Action Button
        btn_start = ctk.CTkButton(
            top_row,
            text="⚡ Start Attendance",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=10,
            height=40,
            command=lambda: self.app.show_page("mark_attendance")
        )
        btn_start.pack(side="right")

        # Stats Cards Row
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 24))

        self.card_students = self._create_stat_card(stats_frame, "👥 Registered Students", "0", COLOR_ACCENT)
        self.card_present = self._create_stat_card(stats_frame, "✅ Present Today", "0", COLOR_SUCCESS)
        self.card_late = self._create_stat_card(stats_frame, "⏰ Late Entries Today", "0", COLOR_WARNING)

        # Recent Activity Card
        recent_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=14)
        recent_card.pack(fill="both", expand=True)

        recent_header = ctk.CTkFrame(recent_card, fg_color="transparent")
        recent_header.pack(fill="x", padx=20, pady=(16, 12))

        lbl_recent = ctk.CTkLabel(
            recent_header,
            text="Today's Live Attendance Feed",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl_recent.pack(side="left")

        btn_refresh = ctk.CTkButton(
            recent_header,
            text="↻ Refresh",
            width=80,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#2D3248",
            hover_color="#373D58",
            corner_radius=8,
            command=self.refresh_stats
        )
        btn_refresh.pack(side="right")

        # Recent Items Container (Scrollable)
        self.recent_container = ctk.CTkScrollableFrame(recent_card, fg_color="transparent")
        self.recent_container.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _create_stat_card(self, parent, title: str, val: str, accent_color: str):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=14, height=100)
        card.pack(side="left", fill="both", expand=True, padx=6)
        card.pack_propagate(False)

        top_line = ctk.CTkFrame(card, height=3, fg_color=accent_color)
        top_line.pack(fill="x")

        t_lbl = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_TEXT_MUTED
        )
        t_lbl.pack(anchor="w", padx=16, pady=(12, 2))

        v_lbl = ctk.CTkLabel(
            card,
            text=val,
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        v_lbl.pack(anchor="w", padx=16)
        return v_lbl

    def _start_clock(self):
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M:%S %p")
        self.lbl_clock.configure(text=f"📅 {date_str}   •   ⏰ {time_str}")
        self.after(1000, self._start_clock)

    def on_enter(self):
        self.refresh_stats()

    def refresh_stats(self):
        stats = excel_manager.get_dashboard_stats()
        self.card_students.configure(text=str(stats["total_students"]))
        self.card_present.configure(text=str(stats["today_present"]))
        self.card_late.configure(text=str(stats["today_late"]))

        # Populate Recent Feed
        for w in self.recent_container.winfo_children():
            w.destroy()

        recent = stats.get("recent_records", [])
        if not recent:
            empty_lbl = ctk.CTkLabel(
                self.recent_container,
                text="No attendance records logged yet today.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=COLOR_TEXT_MUTED
            )
            empty_lbl.pack(pady=40)
            return

        for r in recent:
            row_frame = ctk.CTkFrame(self.recent_container, fg_color="#171A24", corner_radius=8, height=44)
            row_frame.pack(fill="x", pady=3)
            row_frame.pack_propagate(False)

            status = r.get("status", "Present")
            st_color = COLOR_SUCCESS if status == "Present" else COLOR_WARNING

            dot = ctk.CTkLabel(row_frame, text="●", text_color=st_color, font=ctk.CTkFont(size=14))
            dot.pack(side="left", padx=(12, 6))

            name_lbl = ctk.CTkLabel(
                row_frame,
                text=f"{r.get('name')}  ({r.get('roll')})",
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=COLOR_TEXT_MAIN
            )
            name_lbl.pack(side="left", padx=4)

            time_lbl = ctk.CTkLabel(
                row_frame,
                text=r.get("time"),
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=COLOR_TEXT_MUTED
            )
            time_lbl.pack(side="right", padx=16)

            badge = ctk.CTkLabel(
                row_frame,
                text=status,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=st_color
            )
            badge.pack(side="right", padx=10)


# ==============================================================================
# 2. REAL-TIME ATTENDANCE PAGE
# ==============================================================================
class MarkAttendancePage(ctk.CTkFrame):
    def __init__(self, master, app: AttendIQApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.camera = None
        self.is_running = False
        self.cam_thread = None
        self.frame_queue = queue.Queue(maxsize=2)
        self.last_attendance_times = {}  # cooldown cache to avoid spamming toast for same person

        self._build_ui()

    def _build_ui(self):
        # Header Controls
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        title = ctk.CTkLabel(
            title_box,
            text="Real-Time Attendance Monitoring",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        title.pack(anchor="w")

        self.lbl_class_info = ctk.CTkLabel(
            title_box,
            text=f"Class Start Time: {self.app.att_mgr.settings.get('class_start_time', '09:00 AM')} • Liveness Check: Active",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_class_info.pack(anchor="w")

        # Camera Action Button
        self.btn_camera = ctk.CTkButton(
            header,
            text="▶ Start Camera",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLOR_SUCCESS,
            hover_color="#059669",
            corner_radius=10,
            height=40,
            command=self.toggle_camera
        )
        self.btn_camera.pack(side="right")

        # Main Layout: 2 Columns (Left: Video Canvas, Right: Live Activity Log)
        content_split = ctk.CTkFrame(self, fg_color="transparent")
        content_split.pack(fill="both", expand=True)

        # Video Frame Card
        video_card = ctk.CTkFrame(content_split, fg_color=COLOR_CARD, corner_radius=14)
        video_card.pack(side="left", fill="both", expand=True, padx=(0, 12))

        self.video_label = ctk.CTkLabel(
            video_card,
            text="Camera is currently idle.\nClick 'Start Camera' to begin real-time face recognition.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=COLOR_TEXT_MUTED
        )
        self.video_label.pack(fill="both", expand=True, padx=12, pady=12)

        # Live Activity Sidebar Card
        log_card = ctk.CTkFrame(content_split, fg_color=COLOR_CARD, corner_radius=14, width=320)
        log_card.pack(side="right", fill="both", padx=(0, 0))
        log_card.pack_propagate(False)

        log_head = ctk.CTkFrame(log_card, fg_color="transparent")
        log_head.pack(fill="x", padx=16, pady=(16, 10))

        lbl_log = ctk.CTkLabel(
            log_head,
            text="Live Recognition Log",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl_log.pack(side="left")

        self.log_container = ctk.CTkScrollableFrame(log_card, fg_color="transparent")
        self.log_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def on_enter(self):
        # Update class timing notice
        start_time = self.app.att_mgr.settings.get("class_start_time", "09:00 AM")
        liveness = "Active (Blink Required)" if self.app.att_mgr.settings.get("liveness_required", True) else "Disabled"
        self.lbl_class_info.configure(text=f"Class Start Time: {start_time} • Liveness Check: {liveness}")
        self.app.face_engine.reload_faces()

    def toggle_camera(self):
        if self.is_running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        if self.is_running:
            return

        cam_idx = int(self.app.att_mgr.settings.get("webcam_index", 0))
        self.video_label.configure(image=None, text="Initializing Camera Stream...\nPlease ensure webcam access is granted.")
        self.video_label.update()

        try:
            self.camera = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(cam_idx)
            if not self.camera or not self.camera.isOpened():
                # Fallback to standard backend
                self.camera = cv2.VideoCapture(cam_idx)

            if not self.camera.isOpened():
                self.app.toast("Could not connect to webcam. Check index in Settings.", toast_type="danger")
                self.video_label.configure(text="Failed to open webcam.\nPlease check device index in Settings.")
                return
        except Exception as e:
            self.app.toast(f"Camera error: {e}", toast_type="danger")
            return

        self.is_running = True
        self.app.active_camera_page = self
        self.btn_camera.configure(text="⏹ Stop Camera", fg_color=COLOR_DANGER, hover_color="#DC2626")

        # Start Camera Thread
        self.cam_thread = threading.Thread(target=self._camera_worker, daemon=True)
        self.cam_thread.start()

        # Start UI Update Loop
        self.after(30, self._update_video_canvas)

    def stop_camera(self):
        self.is_running = False
        if self.camera:
            try:
                self.camera.release()
            except Exception:
                pass
            self.camera = None

        self.btn_camera.configure(text="▶ Start Camera", fg_color=COLOR_SUCCESS, hover_color="#059669")
        self.video_label.configure(image=None, text="Camera stopped.\nClick 'Start Camera' to resume monitoring.")
        if self.app.active_camera_page == self:
            self.app.active_camera_page = None

    def _camera_worker(self):
        """Worker thread to capture frames and run face recognition + liveness detection."""
        liveness_req = self.app.att_mgr.settings.get("liveness_required", True)

        while self.is_running and self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            # Mirror frame horizontally for natural webcam feel
            frame = cv2.flip(frame, 1)

            # Process frame with face engine
            annotated_frame, recognized_faces = self.app.face_engine.process_frame(
                frame,
                liveness_required=liveness_req
            )

            # Check if any recognized student meets criteria to mark attendance
            for f in recognized_faces:
                if f["is_recognized"] and f["liveness_verified"]:
                    roll = f["roll"]
                    name = f["name"]
                    now_ts = time.time()
                    
                    # 5-second cooldown per person to avoid repeated triggers in same minute
                    if now_ts - self.last_attendance_times.get(roll, 0) > 5.0:
                        self.last_attendance_times[roll] = now_ts
                        self._trigger_mark_attendance(roll, name)

            # Convert to PIL Image for Tkinter
            rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)

            # Put in queue (drop older frame if buffer full)
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put(pil_img)
            time.sleep(0.01)

    def _trigger_mark_attendance(self, roll: str, name: str):
        """Dispatches attendance marking safely to UI thread."""
        def _action():
            success, msg, status = self.app.att_mgr.mark_student_attendance(roll, name)
            if success:
                self.app.toast(f"Attendance Recorded: {name} [{status}]", toast_type="success")
                self._add_log_entry(name, roll, status)
            elif status == "Already Marked":
                self.app.toast(f"{name} ({roll}) has already marked attendance today.", toast_type="warning")
            else:
                self.app.toast(msg, toast_type="danger")

        self.after(0, _action)

    def _add_log_entry(self, name: str, roll: str, status: str):
        curr_time = datetime.now().strftime("%I:%M:%S %p")
        item = ctk.CTkFrame(self.log_container, fg_color="#181B26", corner_radius=8, height=44)
        item.pack(fill="x", pady=3)
        item.pack_propagate(False)

        st_color = COLOR_SUCCESS if status == "Present" else COLOR_WARNING
        dot = ctk.CTkLabel(item, text="●", text_color=st_color, font=ctk.CTkFont(size=14))
        dot.pack(side="left", padx=(10, 4))

        txt = ctk.CTkLabel(
            item,
            text=f"{name}\n{roll}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLOR_TEXT_MAIN,
            justify="left"
        )
        txt.pack(side="left", padx=4)

        time_lbl = ctk.CTkLabel(
            item,
            text=f"{status}\n{curr_time}",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLOR_TEXT_MUTED,
            justify="right"
        )
        time_lbl.pack(side="right", padx=10)

    def _update_video_canvas(self):
        if not self.is_running:
            return

        try:
            pil_img = self.frame_queue.get_nowait()
            # Dynamic resize to fit container
            w = max(self.video_label.winfo_width() - 20, 480)
            h = max(self.video_label.winfo_height() - 20, 360)

            # Preserve aspect ratio
            img_w, img_h = pil_img.size
            ratio = min(w / img_w, h / img_h)
            new_w = int(img_w * ratio)
            new_h = int(img_h * ratio)

            resized = pil_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            ctk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=(new_w, new_h))
            self.video_label.configure(image=ctk_img, text="")
        except queue.Empty:
            pass

        self.after(30, self._update_video_canvas)


# ==============================================================================
# 3. STUDENT REGISTRATION PAGE
# ==============================================================================
class RegisterStudentPage(ctk.CTkFrame):
    def __init__(self, master, app: AttendIQApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.camera = None
        self.is_capturing = False
        self.captured_samples = []
        self.sample_target = 5
        self.cam_thread = None
        self.frame_queue = queue.Queue(maxsize=2)

        self._build_ui()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self,
            text="New Student Biometric Registration",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        title.pack(anchor="w", pady=(0, 16))

        # 2 Column Layout (Left: Form, Right: Camera Preview & Enrollment)
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True)

        # Form Card
        form_card = ctk.CTkFrame(split, fg_color=COLOR_CARD, corner_radius=14, width=380)
        form_card.pack(side="left", fill="both", padx=(0, 14))
        form_card.pack_propagate(False)

        lbl_sec = ctk.CTkLabel(
            form_card,
            text="Student Details",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl_sec.pack(anchor="w", padx=20, pady=(20, 14))

        # Roll Number
        ctk.CTkLabel(form_card, text="Roll Number / ID *", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=20)
        self.ent_roll = ctk.CTkEntry(form_card, placeholder_text="e.g. STU-2026-001", height=38, corner_radius=8)
        self.ent_roll.pack(fill="x", padx=20, pady=(4, 12))

        # Full Name
        ctk.CTkLabel(form_card, text="Full Name *", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=20)
        self.ent_name = ctk.CTkEntry(form_card, placeholder_text="e.g. Alexander Vance", height=38, corner_radius=8)
        self.ent_name.pack(fill="x", padx=20, pady=(4, 12))

        # Course / Branch
        ctk.CTkLabel(form_card, text="Course / Department", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=20)
        self.ent_course = ctk.CTkEntry(form_card, placeholder_text="e.g. Computer Science", height=38, corner_radius=8)
        self.ent_course.pack(fill="x", padx=20, pady=(4, 12))

        # Section
        ctk.CTkLabel(form_card, text="Class / Section", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=20)
        self.ent_sec = ctk.CTkEntry(form_card, placeholder_text="e.g. Section A", height=38, corner_radius=8)
        self.ent_sec.pack(fill="x", padx=20, pady=(4, 16))

        # Progress / Status Text
        self.lbl_progress = ctk.CTkLabel(
            form_card,
            text="Ready. Enter details then click 'Capture Face'.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_MUTED,
            wraplength=320,
            justify="left"
        )
        self.lbl_progress.pack(anchor="w", padx=20, pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(form_card, height=8, corner_radius=4)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 20))

        # Capture Face Button
        self.btn_capture = ctk.CTkButton(
            form_card,
            text="📷 Capture & Register Face",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=10,
            height=42,
            command=self.start_face_enrollment
        )
        self.btn_capture.pack(fill="x", padx=20, pady=(0, 10))

        # Reset Form Button
        btn_clear = ctk.CTkButton(
            form_card,
            text="Clear Form",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color=COLOR_TEXT_MUTED,
            hover_color=COLOR_CARD_HOVER,
            height=32,
            command=self.reset_form
        )
        btn_clear.pack(fill="x", padx=20)

        # Camera Preview Card
        cam_card = ctk.CTkFrame(split, fg_color=COLOR_CARD, corner_radius=14)
        cam_card.pack(side="right", fill="both", expand=True)

        self.cam_preview = ctk.CTkLabel(
            cam_card,
            text="Camera preview will activate when 'Capture Face' is clicked.\n\nEnsure good lighting and face the camera directly.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_TEXT_MUTED
        )
        self.cam_preview.pack(fill="both", expand=True, padx=14, pady=14)

    def on_enter(self):
        self.reset_form()

    def reset_form(self):
        self.stop_camera()
        self.ent_roll.delete(0, "end")
        self.ent_name.delete(0, "end")
        self.ent_course.delete(0, "end")
        self.ent_sec.delete(0, "end")
        self.progress_bar.set(0.0)
        self.lbl_progress.configure(text="Ready. Enter details then click 'Capture Face'.", text_color=COLOR_TEXT_MUTED)
        self.btn_capture.configure(state="normal", text="📷 Capture & Register Face", fg_color=COLOR_ACCENT)

    def start_face_enrollment(self):
        roll = self.ent_roll.get().strip()
        name = self.ent_name.get().strip()

        # Validation
        if not roll or not name:
            self.app.toast("Please fill in Roll Number and Name.", toast_type="warning")
            return

        # Check duplicate roll number BEFORE enrolling
        existing = excel_manager.get_student_by_roll(roll)
        if existing:
            self.app.toast(f"Roll number '{roll}' is already registered!", toast_type="danger")
            messagebox.showerror("Duplicate Roll Number", f"A student with roll number '{roll}' already exists in students.xlsx.\n\nPlease use a unique roll number.")
            return

        cam_idx = int(self.app.att_mgr.settings.get("webcam_index", 0))
        try:
            self.camera = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(cam_idx)
            if not self.camera or not self.camera.isOpened():
                self.camera = cv2.VideoCapture(cam_idx)

            if not self.camera.isOpened():
                self.app.toast("Failed to open webcam.", toast_type="danger")
                return
        except Exception as e:
            self.app.toast(f"Camera error: {e}", toast_type="danger")
            return

        self.is_capturing = True
        self.app.active_camera_page = self
        self.captured_samples.clear()
        self.btn_capture.configure(state="disabled", text="Enrolling...", fg_color="#3730A3")
        self.lbl_progress.configure(text="Looking for face... Please look directly into the camera.", text_color=COLOR_ACCENT)

        self.cam_thread = threading.Thread(target=self._enrollment_worker, args=(roll, name), daemon=True)
        self.cam_thread.start()
        self.after(30, self._update_preview)

    def stop_camera(self):
        self.is_capturing = False
        if self.camera:
            try:
                self.camera.release()
            except Exception:
                pass
            self.camera = None

        if self.app.active_camera_page == self:
            self.app.active_camera_page = None

    def _enrollment_worker(self, roll: str, name: str):
        import face_recognition
        samples = []
        last_capture_time = 0

        while self.is_capturing and self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            frame = cv2.flip(frame, 1)
            display_frame = frame.copy()

            # Downsample for quick face location
            small_rgb = cv2.cvtColor(cv2.resize(frame, (0, 0), fx=0.5, fy=0.5), cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(small_rgb, model="hog")

            now = time.time()
            if len(boxes) == 1:
                top, right, bottom, left = [int(v * 2.0) for v in boxes[0]]
                cv2.rectangle(display_frame, (left, top), (right, bottom), (34, 197, 94), 2)
                cv2.putText(display_frame, f"Sample {len(samples)}/{self.sample_target}", (left, max(top - 10, 20)),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (34, 197, 94), 1, cv2.LINE_AA)

                # Capture sample every 0.6 seconds to allow slight pose variation
                if now - last_capture_time > 0.6 and len(samples) < self.sample_target:
                    samples.append(frame.copy())
                    last_capture_time = now
                    p_val = len(samples) / self.sample_target
                    self.after(0, lambda v=p_val, count=len(samples): self._update_progress_ui(v, count))

            elif len(boxes) > 1:
                # Multiple faces warning
                cv2.putText(display_frame, "MULTIPLE FACES DETECTED - 1 FACE REQUIRED", (30, 40),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (30, 64, 239), 2, cv2.LINE_AA)
            else:
                # No face
                cv2.putText(display_frame, "Looking for face... Please look directly into camera", (30, 40),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, (20, 184, 245), 1, cv2.LINE_AA)

            # Put display frame in queue
            pil_img = Image.fromarray(cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB))
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            self.frame_queue.put(pil_img)

            # Check if all samples collected
            if len(samples) >= self.sample_target:
                break

            time.sleep(0.02)

        # Process and complete enrollment
        if len(samples) >= self.sample_target:
            self.after(0, lambda: self._finalize_registration(roll, name, samples))
        else:
            self.after(0, lambda: self.lbl_progress.configure(text="Registration cancelled.", text_color=COLOR_WARNING))

    def _update_progress_ui(self, p_val: float, count: int):
        self.progress_bar.set(p_val)
        self.lbl_progress.configure(
            text=f"Captured {count}/{self.sample_target} samples. Tilt head slightly for best angle...",
            text_color=COLOR_SUCCESS
        )

    def _finalize_registration(self, roll: str, name: str, samples: list):
        self.lbl_progress.configure(text="Computing 128-d facial encodings and saving local data...", text_color=COLOR_ACCENT)
        self.stop_camera()

        # Enroll face with engine
        ok, msg, face_id = self.app.face_engine.enroll_face(roll, name, samples)
        if not ok:
            self.app.toast(f"Enrollment error: {msg}", toast_type="danger")
            self.lbl_progress.configure(text=f"Enrollment failed: {msg}", text_color=COLOR_DANGER)
            self.btn_capture.configure(state="normal", text="📷 Retry Registration", fg_color=COLOR_ACCENT)
            return

        # Register in Excel
        course = self.ent_course.get().strip() or "N/A"
        section = self.ent_sec.get().strip() or "N/A"

        reg_ok, reg_msg = excel_manager.register_student(roll, name, course, section, face_id)
        if reg_ok:
            self.app.toast(f"Student {name} registered successfully!", toast_type="success")
            self.lbl_progress.configure(text=f"✔ Registered: {name} ({roll})", text_color=COLOR_SUCCESS)
            self.progress_bar.set(1.0)
            messagebox.showinfo("Registration Successful", f"Student successfully registered:\n\nName: {name}\nRoll: {roll}\nCourse: {course}\nFace ID: {face_id}\n\nRecord saved in data/students.xlsx.")
            self.reset_form()
            # Refresh engine faces
            self.app.face_engine.reload_faces()
        else:
            self.app.toast(reg_msg, toast_type="danger")
            self.lbl_progress.configure(text=reg_msg, text_color=COLOR_DANGER)
            self.btn_capture.configure(state="normal", text="📷 Try Again", fg_color=COLOR_ACCENT)

    def _update_preview(self):
        if not self.is_capturing:
            return

        try:
            pil_img = self.frame_queue.get_nowait()
            w = max(self.cam_preview.winfo_width() - 20, 360)
            h = max(self.cam_preview.winfo_height() - 20, 280)
            img_w, img_h = pil_img.size
            ratio = min(w / img_w, h / img_h)
            new_w = int(img_w * ratio)
            new_h = int(img_h * ratio)
            resized = pil_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            ctk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=(new_w, new_h))
            self.cam_preview.configure(image=ctk_img, text="")
        except queue.Empty:
            pass

        self.after(30, self._update_preview)


# ==============================================================================
# 4. STUDENTS PAGE
# ==============================================================================
class StudentsPage(ctk.CTkFrame):
    def __init__(self, master, app: AttendIQApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # Header Row
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 16))

        title = ctk.CTkLabel(
            head,
            text="Registered Students Directory",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        title.pack(side="left")

        # Search Bar
        self.ent_search = ctk.CTkEntry(
            head,
            placeholder_text="🔍 Search student name or roll...",
            width=280,
            height=36,
            corner_radius=8
        )
        self.ent_search.pack(side="right", padx=(10, 0))
        self.ent_search.bind("<KeyRelease>", lambda e: self.load_students())

        # Action Buttons Row
        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 12))

        btn_view = ctk.CTkButton(
            action_row,
            text="👁 View Photo & Stats",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=8,
            height=32,
            command=self.view_selected_student
        )
        btn_view.pack(side="left", padx=(0, 8))

        btn_delete = ctk.CTkButton(
            action_row,
            text="🗑 Delete Student",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_DANGER,
            hover_color="#DC2626",
            corner_radius=8,
            height=32,
            command=self.delete_selected_student
        )
        btn_delete.pack(side="left", padx=(0, 8))

        btn_refresh = ctk.CTkButton(
            action_row,
            text="↻ Refresh",
            font=ctk.CTkFont(size=12),
            fg_color="#2D3248",
            hover_color="#373D58",
            corner_radius=8,
            height=32,
            command=self.load_students
        )
        btn_refresh.pack(side="right")

        # Students Table Container
        table_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=14)
        table_card.pack(fill="both", expand=True)

        # Style Treeview for dark theme
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Custom.Treeview",
            background=COLOR_CARD,
            foreground=COLOR_TEXT_MAIN,
            fieldbackground=COLOR_CARD,
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#252A3C",
            foreground="#E2E8F0",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=6
        )
        style.map("Custom.Treeview", background=[("selected", COLOR_ACCENT)])

        columns = ("Roll Number", "Name", "Course", "Section", "Registration Date", "Face ID")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", style="Custom.Treeview", selectmode="browse")

        for col in columns:
            self.tree.heading(col, text=col)
            width = 160 if col in ("Name", "Registration Date") else 110
            self.tree.column(col, anchor="center" if col != "Name" else "w", width=width)

        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=12)
        scrollbar.pack(side="right", fill="y", padx=(0, 12), pady=12)

    def on_enter(self):
        self.load_students()

    def load_students(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        df = excel_manager.get_all_students()
        if df.empty:
            return

        query = self.ent_search.get().strip().lower()
        if query:
            df = df[
                df["Roll Number"].astype(str).str.lower().str.contains(query) |
                df["Name"].astype(str).str.lower().str.contains(query)
            ]

        for _, row in df.iterrows():
            self.tree.insert("", "end", values=(
                row.get("Roll Number", ""),
                row.get("Name", ""),
                row.get("Course", ""),
                row.get("Section", ""),
                row.get("Registration Date", ""),
                row.get("Face ID", "")
            ))

    def view_selected_student(self):
        sel = self.tree.selection()
        if not sel:
            self.app.toast("Please select a student from the list.", toast_type="warning")
            return

        vals = self.tree.item(sel[0], "values")
        roll, name, course, sec, reg_date, face_id = vals

        # Modal Window
        win = ctk.CTkToplevel(self)
        win.title(f"Student Profile – {name}")
        win.geometry("520x540")
        win.minsize(480, 500)
        win.configure(fg_color=COLOR_BG_DARK)
        win.grab_set()

        # Face Photo Frame
        photo_box = ctk.CTkFrame(win, fg_color=COLOR_CARD, corner_radius=12, width=180, height=180)
        photo_box.pack(pady=(24, 16))
        photo_box.pack_propagate(False)

        jpg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_data", "registered_faces", f"{face_id}.jpg")
        if os.path.exists(jpg_path):
            try:
                pil_face = Image.open(jpg_path).resize((160, 160), Image.Resampling.LANCZOS)
                ctk_face = ctk.CTkImage(light_image=pil_face, dark_image=pil_face, size=(160, 160))
                lbl_photo = ctk.CTkLabel(photo_box, image=ctk_face, text="")
                lbl_photo.pack(expand=True)
            except Exception:
                ctk.CTkLabel(photo_box, text="Image Load Error", text_color=COLOR_TEXT_MUTED).pack(expand=True)
        else:
            ctk.CTkLabel(photo_box, text="No Photo Found", text_color=COLOR_TEXT_MUTED).pack(expand=True)

        # Profile Details Card
        info_card = ctk.CTkFrame(win, fg_color=COLOR_CARD, corner_radius=12)
        info_card.pack(fill="x", padx=24, pady=(0, 16))

        details = [
            ("Full Name:", name),
            ("Roll Number:", roll),
            ("Course / Branch:", course),
            ("Section:", sec),
            ("Registered On:", reg_date),
            ("Face ID Reference:", face_id)
        ]

        for lbl, val in details:
            r = ctk.CTkFrame(info_card, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(r, text=lbl, font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_MUTED, width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MAIN, anchor="w").pack(side="left", fill="x", expand=True)

        # Overall Attendance Stats
        stats = excel_manager.get_student_attendance_stats(roll)
        stats_box = ctk.CTkFrame(win, fg_color="#181B26", corner_radius=10)
        stats_box.pack(fill="x", padx=24, pady=(0, 20))

        st_lbl = ctk.CTkLabel(
            stats_box,
            text=f"Total Classes Held: {stats['total_sessions']}  |  Attended: {stats['attended']}  |  Attendance: {stats['percentage']}%",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLOR_SUCCESS if stats['percentage'] >= 75 else COLOR_WARNING
        )
        st_lbl.pack(pady=10)

        ctk.CTkButton(win, text="Close", width=120, height=36, corner_radius=8, command=win.destroy).pack()

    def delete_selected_student(self):
        sel = self.tree.selection()
        if not sel:
            self.app.toast("Please select a student to delete.", toast_type="warning")
            return

        vals = self.tree.item(sel[0], "values")
        roll, name = vals[0], vals[1]

        confirm = messagebox.askyesno(
            "Confirm Student Deletion",
            f"Are you sure you want to delete student:\n\n{name} (Roll: {roll})?\n\nThis will remove their biometric face data. Historical attendance logs in attendance.xlsx will be preserved."
        )

        if confirm:
            ok, msg, face_id = excel_manager.delete_student(roll)
            if ok:
                if face_id:
                    self.app.face_engine.delete_face_data(face_id)
                self.app.toast(f"Student {name} deleted.", toast_type="success")
                self.load_students()
            else:
                self.app.toast(msg, toast_type="danger")


# ==============================================================================
# 5. ATTENDANCE RECORDS PAGE
# ==============================================================================
class AttendanceRecordsPage(ctk.CTkFrame):
    def __init__(self, master, app: AttendIQApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build_ui()

    def _build_ui(self):
        # Header Row
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 16))

        title = ctk.CTkLabel(
            head,
            text="Attendance Logs & Reports",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        title.pack(side="left")

        # Filters Bar
        filter_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        filter_card.pack(fill="x", pady=(0, 14))

        f_inner = ctk.CTkFrame(filter_card, fg_color="transparent")
        f_inner.pack(fill="x", padx=16, pady=12)

        # Search query
        ctk.CTkLabel(f_inner, text="Search:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.ent_search = ctk.CTkEntry(f_inner, placeholder_text="Name or Roll...", width=160, height=32, corner_radius=6)
        self.ent_search.pack(side="left", padx=(0, 14))
        self.ent_search.bind("<KeyRelease>", lambda e: self.load_records())

        # Date filter
        ctk.CTkLabel(f_inner, text="Date:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.ent_date = ctk.CTkEntry(f_inner, placeholder_text="YYYY-MM-DD", width=120, height=32, corner_radius=6)
        self.ent_date.pack(side="left", padx=(0, 14))
        self.ent_date.bind("<KeyRelease>", lambda e: self.load_records())

        # Status filter dropdown
        ctk.CTkLabel(f_inner, text="Status:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(0, 6))
        self.opt_status = ctk.CTkOptionMenu(
            f_inner,
            values=["All", "Present", "Late"],
            width=100,
            height=32,
            corner_radius=6,
            command=lambda v: self.load_records()
        )
        self.opt_status.pack(side="left", padx=(0, 14))

        # Reset button
        btn_reset = ctk.CTkButton(
            f_inner,
            text="Reset",
            width=65,
            height=32,
            fg_color="#2D3248",
            hover_color="#373D58",
            corner_radius=6,
            command=self.reset_filters
        )
        btn_reset.pack(side="left")

        # Export Button
        btn_export = ctk.CTkButton(
            f_inner,
            text="📥 Export to Excel",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=8,
            height=32,
            command=self.export_records
        )
        btn_export.pack(side="right")

        # Table Container
        table_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=14)
        table_card.pack(fill="both", expand=True)

        columns = ("Roll Number", "Student Name", "Date", "Time", "Status")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", style="Custom.Treeview", selectmode="browse")

        for col in columns:
            self.tree.heading(col, text=col)
            width = 180 if col == "Student Name" else 130
            self.tree.column(col, anchor="center" if col != "Student Name" else "w", width=width)

        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=12)
        scrollbar.pack(side="right", fill="y", padx=(0, 12), pady=12)

    def on_enter(self):
        self.load_records()

    def reset_filters(self):
        self.ent_search.delete(0, "end")
        self.ent_date.delete(0, "end")
        self.opt_status.set("All")
        self.load_records()

    def load_records(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        df = excel_manager.get_all_attendance()
        if df.empty:
            return

        query = self.ent_search.get().strip().lower()
        date_q = self.ent_date.get().strip()
        status_q = self.opt_status.get()

        if query:
            df = df[
                df["Roll Number"].astype(str).str.lower().str.contains(query) |
                df["Student Name"].astype(str).str.lower().str.contains(query)
            ]

        if date_q:
            df = df[df["Date"].astype(str).str.contains(date_q)]

        if status_q and status_q != "All":
            df = df[df["Status"].astype(str).str.lower() == status_q.lower()]

        for _, row in df.iloc[::-1].iterrows():
            self.tree.insert("", "end", values=(
                row.get("Roll Number", ""),
                row.get("Student Name", ""),
                row.get("Date", ""),
                row.get("Time", ""),
                row.get("Status", "Present")
            ))

    def export_records(self):
        default_dir = self.app.att_mgr.settings.get("export_directory", os.path.expanduser("~"))
        suggested_name = f"AttendIQ_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        initial_file = os.path.join(default_dir, suggested_name)

        save_path = filedialog.asksaveasfilename(
            initialdir=default_dir,
            initialfile=suggested_name,
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")]
        )

        if not save_path:
            return

        date_q = self.ent_date.get().strip() or None
        roll_q = self.ent_search.get().strip() or None
        status_q = self.opt_status.get()

        ok, msg = excel_manager.export_attendance_report(
            save_path,
            filter_date=date_q,
            filter_roll=roll_q,
            filter_status=status_q
        )

        if ok:
            self.app.toast("Attendance report exported successfully!", toast_type="success")
            messagebox.showinfo("Export Successful", f"Attendance records exported to:\n\n{save_path}")
        else:
            self.app.toast(msg, toast_type="danger")
            messagebox.showerror("Export Failed", msg)


# ==============================================================================
# 6. SETTINGS PAGE
# ==============================================================================
class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, app: AttendIQApp):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._build_ui()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self,
            text="Application Settings",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        title.pack(anchor="w", pady=(0, 16))

        scroll_settings = ctk.CTkScrollableFrame(self, fg_color=COLOR_CARD, corner_radius=14)
        scroll_settings.pack(fill="both", expand=True)

        # 1. Class Timing
        self._create_section_header(scroll_settings, "⏰ Class Schedule & Late Entry Rule")
        ctk.CTkLabel(
            scroll_settings,
            text="Attendance marked after this start time is automatically classified as 'Late'.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 6))

        self.ent_start_time = ctk.CTkEntry(scroll_settings, placeholder_text="09:00 AM", width=220, height=36, corner_radius=8)
        self.ent_start_time.pack(anchor="w", padx=20, pady=(0, 16))

        # 2. Recognition Confidence Threshold
        self._create_section_header(scroll_settings, "🎯 Face Recognition Confidence Threshold")
        ctk.CTkLabel(
            scroll_settings,
            text="Lower values mean stricter facial matching. Recommended: 0.50.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 6))

        slider_box = ctk.CTkFrame(scroll_settings, fg_color="transparent")
        slider_box.pack(anchor="w", padx=20, pady=(0, 16))

        self.slider_tol = ctk.CTkSlider(
            slider_box,
            from_=0.35,
            to=0.65,
            number_of_steps=30,
            width=260,
            command=self._on_slider_change
        )
        self.slider_tol.pack(side="left", padx=(0, 12))

        self.lbl_tol_val = ctk.CTkLabel(
            slider_box,
            text="0.50",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_tol_val.pack(side="left")

        # 3. Webcam Selection
        self._create_section_header(scroll_settings, "📹 Webcam Device Selection")
        ctk.CTkLabel(
            scroll_settings,
            text="Select internal built-in camera (0) or external USB camera (1, 2).",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 6))

        self.opt_cam = ctk.CTkOptionMenu(
            scroll_settings,
            values=["Camera 0 (Default)", "Camera 1 (External)", "Camera 2"],
            width=220,
            height=36,
            corner_radius=8
        )
        self.opt_cam.pack(anchor="w", padx=20, pady=(0, 16))

        # 4. Feature Toggles
        self._create_section_header(scroll_settings, "🔔 Audio & Anti-Spoofing Features")

        self.sw_sound = ctk.CTkSwitch(
            scroll_settings,
            text="Enable Confirmation Audio Chime on Attendance",
            font=ctk.CTkFont(size=13),
            progress_color=COLOR_ACCENT
        )
        self.sw_sound.pack(anchor="w", padx=20, pady=(4, 10))

        self.sw_liveness = ctk.CTkSwitch(
            scroll_settings,
            text="Enable Blink-Based Liveness Verification (Anti-Photo Spoofing)",
            font=ctk.CTkFont(size=13),
            progress_color=COLOR_ACCENT
        )
        self.sw_liveness.pack(anchor="w", padx=20, pady=(4, 16))

        # 5. Export Directory
        self._create_section_header(scroll_settings, "📁 Default Attendance Export Folder")
        exp_box = ctk.CTkFrame(scroll_settings, fg_color="transparent")
        exp_box.pack(fill="x", padx=20, pady=(0, 24))

        self.ent_export = ctk.CTkEntry(exp_box, width=380, height=36, corner_radius=8)
        self.ent_export.pack(side="left", padx=(0, 10))

        btn_browse = ctk.CTkButton(
            exp_box,
            text="Browse...",
            width=90,
            height=36,
            corner_radius=8,
            fg_color="#2D3248",
            hover_color="#373D58",
            command=self.browse_export_dir
        )
        btn_browse.pack(side="left")

        # Bottom Action Buttons
        btn_row = ctk.CTkFrame(scroll_settings, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(10, 20))

        btn_save = ctk.CTkButton(
            btn_row,
            text="💾 Save Settings",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=10,
            height=42,
            width=160,
            command=self.save_settings
        )
        btn_save.pack(side="left", padx=(0, 12))

        btn_reset = ctk.CTkButton(
            btn_row,
            text="↺ Reset to Defaults",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color=COLOR_WARNING,
            hover_color=COLOR_CARD_HOVER,
            corner_radius=10,
            height=42,
            command=self.reset_defaults
        )
        btn_reset.pack(side="left")

    def _create_section_header(self, parent, text: str):
        lbl = ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl.pack(anchor="w", padx=20, pady=(16, 4))

    def _on_slider_change(self, val):
        self.lbl_tol_val.configure(text=f"{val:.2f}")

    def browse_export_dir(self):
        folder = filedialog.askdirectory(initialdir=self.ent_export.get() or os.path.expanduser("~"))
        if folder:
            self.ent_export.delete(0, "end")
            self.ent_export.insert(0, folder)

    def on_enter(self):
        settings = self.app.att_mgr.settings
        self.ent_start_time.delete(0, "end")
        self.ent_start_time.insert(0, settings.get("class_start_time", "09:00 AM"))

        tol = float(settings.get("face_confidence_threshold", 0.50))
        self.slider_tol.set(tol)
        self.lbl_tol_val.configure(text=f"{tol:.2f}")

        cam_idx = settings.get("webcam_index", 0)
        self.opt_cam.set(f"Camera {cam_idx}" + (" (Default)" if cam_idx == 0 else ""))

        if settings.get("sound_enabled", True):
            self.sw_sound.select()
        else:
            self.sw_sound.deselect()

        if settings.get("liveness_required", True):
            self.sw_liveness.select()
        else:
            self.sw_liveness.deselect()

        self.ent_export.delete(0, "end")
        self.ent_export.insert(0, settings.get("export_directory", os.path.join(os.path.expanduser("~"), "Desktop")))

    def save_settings(self):
        start_time = self.ent_start_time.get().strip() or "09:00 AM"
        tol = round(float(self.slider_tol.get()), 2)

        cam_str = self.opt_cam.get()
        cam_idx = 0
        if "1" in cam_str:
            cam_idx = 1
        elif "2" in cam_str:
            cam_idx = 2

        sound = bool(self.sw_sound.get())
        liveness = bool(self.sw_liveness.get())
        export_dir = self.ent_export.get().strip() or os.path.join(os.path.expanduser("~"), "Desktop")

        new_settings = {
            "class_start_time": start_time,
            "face_confidence_threshold": tol,
            "webcam_index": cam_idx,
            "sound_enabled": sound,
            "liveness_required": liveness,
            "export_directory": export_dir
        }

        ok = self.app.att_mgr.save_settings(new_settings)
        if ok:
            self.app.face_engine.set_tolerance(tol)
            self.app.toast("Settings saved successfully!", toast_type="success")
        else:
            self.app.toast("Failed to save settings.", toast_type="danger")

    def reset_defaults(self):
        confirm = messagebox.askyesno("Reset Settings", "Reset all settings to original defaults?")
        if confirm:
            self.app.att_mgr.reset_settings()
            self.on_enter()
            self.app.toast("Settings reset to defaults.", toast_type="info")


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
if __name__ == "__main__":
    app = AttendIQApp()
    app.mainloop()
