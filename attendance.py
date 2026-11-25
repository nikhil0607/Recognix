"""
attendance.py
Attendance management logic and configuration handler for AttendIQ.
Handles:
- Settings (JSON config)
- Class timing / Late vs Present classification
- Daily duplicate prevention
- Audio notifications (winsound)
- Integration with excel_manager
"""

import os
import json
import threading
from datetime import datetime, time
import excel_manager

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_SETTINGS = {
    "class_start_time": "09:00 AM",
    "face_confidence_threshold": 0.50,
    "webcam_index": 0,
    "sound_enabled": True,
    "liveness_required": True,
    "export_directory": os.path.join(os.path.expanduser("~"), "Desktop")
}


class AttendanceManager:
    def __init__(self):
        self.settings = self.load_settings()

    def load_settings(self) -> dict:
        """Loads user settings from config.json or returns default settings."""
        if not os.path.exists(CONFIG_FILE):
            self.save_settings(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
        except Exception as e:
            print(f"[AttendanceManager] Error loading config: {e}")
            return dict(DEFAULT_SETTINGS)

    def save_settings(self, new_settings: dict) -> bool:
        """Saves settings dictionary to config.json."""
        try:
            self.settings = dict(new_settings)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            print(f"[AttendanceManager] Error saving config: {e}")
            return False

    def reset_settings(self) -> dict:
        """Resets settings to defaults and saves them."""
        self.save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)

    def is_late(self) -> bool:
        """
        Determines if the current time is after the configured class_start_time.
        Supported formats: '09:00 AM', '9:00 AM', '09:00', '9:00'.
        """
        time_str = self.settings.get("class_start_time", "09:00 AM").strip()
        now = datetime.now().time()

        # Parse configured start time
        parsed_time = None
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
            try:
                parsed_time = datetime.strptime(time_str, fmt).time()
                break
            except ValueError:
                continue

        if not parsed_time:
            # Fallback to 9:00 AM
            parsed_time = time(9, 0)

        return now > parsed_time

    def play_sound(self, sound_type: str = "success"):
        """Plays non-blocking audio feedback if sound is enabled."""
        if not self.settings.get("sound_enabled", True):
            return

        def _sound_thread():
            try:
                import winsound
                if sound_type == "success":
                    # Two cheerful short beeps
                    winsound.Beep(1046, 120)  # C6
                    winsound.Beep(1318, 160)  # E6
                elif sound_type == "warning":
                    # Alert tone
                    winsound.Beep(659, 150)   # E5
                    winsound.Beep(523, 200)   # C5
            except Exception:
                # Silently ignore if audio hardware is unavailable
                pass

        threading.Thread(target=_sound_thread, daemon=True).start()

    def mark_student_attendance(self, roll_number: str, student_name: str) -> tuple[bool, str, str]:
        """
        Marks attendance for the student with duplicate prevention and late entry detection.
        Returns:
            (success: bool, message: str, status: str)
            status is 'Present', 'Late', or 'Already Marked'
        """
        roll_number = str(roll_number).strip()

        # Check if already marked today
        if excel_manager.has_marked_today(roll_number):
            return False, f"Attendance already recorded today for {student_name} ({roll_number}).", "Already Marked"

        # Determine Present vs Late
        status = "Late" if self.is_late() else "Present"

        success, msg = excel_manager.mark_attendance(roll_number, student_name, status=status)
        if success:
            self.play_sound("success")
            return True, f"Attendance marked for {student_name} ({roll_number}) as [{status}].", status
        else:
            return False, msg, "Error"
