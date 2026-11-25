"""
face_engine.py
Core Facial Recognition, Liveness Detection, and Face Enrollment Engine for AttendIQ.
Uses:
- OpenCV (cv2) for video capture, processing, and visualization
- face_recognition (dlib-based) for face detection, 68-point landmarks, and 128-d encodings
- NumPy for vector distance, averaging, and .npy persistence
"""

import os
import glob
import time
import cv2
import numpy as np
import face_recognition
import excel_manager

FACE_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_data")
REGISTERED_FACES_DIR = os.path.join(FACE_DATA_DIR, "registered_faces")

EYE_AR_THRESH = 0.22      # Eye aspect ratio threshold to consider eye closed
EYE_AR_OPEN_THRESH = 0.26 # Eye aspect ratio threshold to consider eye reopened
CONSEC_FRAMES_BLINK = 1   # Number of consecutive frames eyes must be closed


def calculate_ear(eye_points: list[tuple[int, int]]) -> float:
    """
    Computes Eye Aspect Ratio (EAR) for a 6-point eye landmark set:
    EAR = (|p2 - p6| + |p3 - p5|) / (2 * |p1 - p4|)
    """
    pts = np.array(eye_points, dtype=np.float32)
    # Vertical distances
    dist_a = np.linalg.norm(pts[1] - pts[5])
    dist_b = np.linalg.norm(pts[2] - pts[4])
    # Horizontal distance
    dist_c = np.linalg.norm(pts[0] - pts[3])
    if dist_c == 0:
        return 0.3
    ear = (dist_a + dist_b) / (2.0 * dist_c)
    return float(ear)


class FaceEngine:
    def __init__(self, tolerance: float = 0.50):
        self.tolerance = tolerance
        self.known_encodings = []      # list of np.ndarray
        self.known_rolls = []          # list of str
        self.known_names = []          # list of str
        self.known_face_ids = []       # list of str
        
        # Per-person liveness tracking state during active recognition:
        # roll -> {"eye_closed_frames": int, "blinked": bool, "last_seen": float}
        self.liveness_tracker = {}

        self.ensure_dirs()
        self.reload_faces()

    def ensure_dirs(self):
        """Ensures registered faces storage directory exists."""
        os.makedirs(REGISTERED_FACES_DIR, exist_ok=True)

    def set_tolerance(self, tolerance: float):
        """Update face matching confidence threshold."""
        self.tolerance = float(tolerance)

    def reload_faces(self):
        """
        Loads all saved face encodings from disk and links them with student records.
        Cached in memory to prevent slow disk reads on every video frame.
        """
        self.known_encodings.clear()
        self.known_rolls.clear()
        self.known_names.clear()
        self.known_face_ids.clear()
        self.liveness_tracker.clear()

        self.ensure_dirs()
        students_df = excel_manager.get_all_students()
        if students_df.empty:
            return

        # Map face_id to student record
        student_map = {}
        for _, row in students_df.iterrows():
            fid = str(row.get("Face ID", "")).strip()
            if fid:
                student_map[fid] = {
                    "roll": str(row.get("Roll Number", "")).strip(),
                    "name": str(row.get("Name", "")).strip()
                }

        npy_files = glob.glob(os.path.join(REGISTERED_FACES_DIR, "*.npy"))
        for npy_path in npy_files:
            try:
                base_name = os.path.splitext(os.path.basename(npy_path))[0]
                encoding = np.load(npy_path)
                
                # Check if this face_id belongs to a registered student
                if base_name in student_map:
                    self.known_encodings.append(encoding)
                    self.known_face_ids.append(base_name)
                    self.known_rolls.append(student_map[base_name]["roll"])
                    self.known_names.append(student_map[base_name]["name"])
            except Exception as e:
                print(f"[FaceEngine] Error loading {npy_path}: {e}")

    def enroll_face(self, roll_number: str, name: str, face_samples: list[np.ndarray]) -> tuple[bool, str, str | None]:
        """
        Enrolls a student using collected face frames (RGB or BGR numpy arrays):
        1. Generates 128-d encodings for all valid samples.
        2. Averages encodings for higher accuracy.
        3. Saves <face_id>.npy and <face_id>.jpg to disk.
        Returns:
            (success: bool, message: str, face_id: str | None)
        """
        if not face_samples:
            return False, "No face samples provided for enrollment.", None

        valid_encodings = []
        best_face_img = None

        for sample in face_samples:
            # Ensure RGB for face_recognition
            if len(sample.shape) == 3 and sample.shape[2] == 3:
                rgb_img = cv2.cvtColor(sample, cv2.COLOR_BGR2RGB) if sample.flags.c_contiguous else sample
            else:
                rgb_img = sample

            boxes = face_recognition.face_locations(rgb_img, model="hog")
            if len(boxes) == 1:
                encs = face_recognition.face_encodings(rgb_img, known_face_locations=boxes)
                if encs:
                    valid_encodings.append(encs[0])
                    if best_face_img is None:
                        # Crop or keep the best face
                        top, right, bottom, left = boxes[0]
                        # Add a small padding around the face for clean preview
                        h, w, _ = sample.shape
                        pad_h = int((bottom - top) * 0.2)
                        pad_w = int((right - left) * 0.2)
                        c_top = max(0, top - pad_h)
                        c_bot = min(h, bottom + pad_h)
                        c_left = max(0, left - pad_w)
                        c_right = min(w, right + pad_w)
                        best_face_img = sample[c_top:c_bot, c_left:c_right].copy()

        if len(valid_encodings) < 2:
            return False, "Insufficient clear face angles captured. Please ensure good lighting and look directly into the camera.", None

        # Average the encodings to build a robust facial signature
        avg_encoding = np.mean(valid_encodings, axis=0)
        # Normalize the embedding
        avg_encoding = avg_encoding / np.linalg.norm(avg_encoding)

        # Generate unique Face ID
        timestamp = int(time.time())
        clean_roll = "".join(c for c in roll_number if c.isalnum() or c in ("-", "_"))
        face_id = f"{clean_roll}_{timestamp}"

        # Save files
        npy_path = os.path.join(REGISTERED_FACES_DIR, f"{face_id}.npy")
        jpg_path = os.path.join(REGISTERED_FACES_DIR, f"{face_id}.jpg")

        try:
            np.save(npy_path, avg_encoding)
            if best_face_img is not None and best_face_img.size > 0:
                cv2.imwrite(jpg_path, best_face_img)
            else:
                # Fallback to the first raw sample
                cv2.imwrite(jpg_path, face_samples[0])

            # Refresh in-memory cache
            self.reload_faces()
            return True, "Face enrolled successfully.", face_id
        except Exception as e:
            return False, f"Failed to save face data files: {e}", None

    def delete_face_data(self, face_id: str):
        """Removes student face image and encoding from disk and in-memory cache."""
        if not face_id:
            return
        npy_path = os.path.join(REGISTERED_FACES_DIR, f"{face_id}.npy")
        jpg_path = os.path.join(REGISTERED_FACES_DIR, f"{face_id}.jpg")

        for p in (npy_path, jpg_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception as e:
                    print(f"[FaceEngine] Error removing {p}: {e}")

        self.reload_faces()

    def process_frame(
        self,
        frame: np.ndarray,
        liveness_required: bool = True
    ) -> tuple[np.ndarray, list[dict]]:
        """
        Processes a single camera video frame:
        1. Downsamples for high-speed face detection.
        2. Detects face locations and 128-d encodings.
        3. Matches against cached registered faces.
        4. Calculates Eye Aspect Ratio (EAR) for blink liveness detection.
        5. Draws bounding boxes, student information, and liveness status on the frame.
        
        Returns:
            annotated_frame: np.ndarray (BGR)
            recognized_faces: list of dict [
                {
                    "roll": str,
                    "name": str,
                    "distance": float,
                    "liveness_verified": bool,
                    "box": (top, right, bottom, left)
                }
            ]
        """
        # Downscale frame for fast inference (0.5x scale)
        scale_factor = 0.5
        small_frame = cv2.resize(frame, (0, 0), fx=scale_factor, fy=scale_factor)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Detect face boxes
        face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        # Detect 68-point facial landmarks for blink liveness
        face_landmarks_list = face_recognition.face_landmarks(rgb_small_frame, face_locations) if face_locations else []

        curr_time = time.time()
        results = []

        # Clean stale tracked faces (older than 3 seconds)
        stale_keys = [k for k, v in self.liveness_tracker.items() if curr_time - v.get("last_seen", 0) > 3.0]
        for k in stale_keys:
            del self.liveness_tracker[k]

        annotated_frame = frame.copy()

        for idx, (face_loc, encoding) in enumerate(zip(face_locations, face_encodings)):
            # Scale coordinates back up to original frame
            s_top, s_right, s_bottom, s_left = face_loc
            top = int(s_top / scale_factor)
            right = int(s_right / scale_factor)
            bottom = int(s_bottom / scale_factor)
            left = int(s_left / scale_factor)

            # Determine identity
            name = "Unknown Person"
            roll = ""
            best_distance = 1.0
            is_recognized = False

            if self.known_encodings:
                distances = face_recognition.face_distance(self.known_encodings, encoding)
                min_idx = int(np.argmin(distances))
                min_dist = float(distances[min_idx])
                best_distance = min_dist

                if min_dist <= self.tolerance:
                    name = self.known_names[min_idx]
                    roll = self.known_rolls[min_idx]
                    is_recognized = True

            # Calculate Liveness / Blink
            liveness_ok = not liveness_required  # Default true if liveness disabled
            tracker_key = roll if is_recognized else f"unk_{left}_{top}"

            if tracker_key not in self.liveness_tracker:
                self.liveness_tracker[tracker_key] = {
                    "closed_frames": 0,
                    "blinked": False,
                    "last_seen": curr_time
                }

            person_state = self.liveness_tracker[tracker_key]
            person_state["last_seen"] = curr_time

            if liveness_required and idx < len(face_landmarks_list):
                landmarks = face_landmarks_list[idx]
                left_eye = landmarks.get("left_eye", [])
                right_eye = landmarks.get("right_eye", [])

                if len(left_eye) == 6 and len(right_eye) == 6:
                    left_ear = calculate_ear(left_eye)
                    right_ear = calculate_ear(right_eye)
                    avg_ear = (left_ear + right_ear) / 2.0

                    if avg_ear < EYE_AR_THRESH:
                        person_state["closed_frames"] += 1
                    else:
                        if person_state["closed_frames"] >= CONSEC_FRAMES_BLINK and avg_ear >= EYE_AR_OPEN_THRESH:
                            person_state["blinked"] = True
                        person_state["closed_frames"] = 0

                liveness_ok = person_state.get("blinked", False)

            # Append to recognized face results
            face_data = {
                "roll": roll,
                "name": name,
                "distance": best_distance,
                "liveness_verified": liveness_ok,
                "is_recognized": is_recognized,
                "box": (top, right, bottom, left)
            }
            results.append(face_data)

            # Draw visual bounding box and info badge
            self._draw_overlay(annotated_frame, top, right, bottom, left, name, roll, is_recognized, liveness_ok, liveness_required)

        return annotated_frame, results

    def _draw_overlay(
        self,
        img: np.ndarray,
        top: int,
        right: int,
        bottom: int,
        left: int,
        name: str,
        roll: str,
        is_recognized: bool,
        liveness_ok: bool,
        liveness_required: bool
    ):
        """
        Draws modern rounded biometric target brackets, header pills,
        and liveness indicators.
        """
        # Colors (BGR)
        COLOR_RECOGNIZED = (34, 197, 94)    # Emerald Green
        COLOR_UNKNOWN = (30, 64, 239)       # Bright Crimson/Orange
        COLOR_WARNING = (20, 184, 245)      # Amber / Golden

        box_color = COLOR_RECOGNIZED if is_recognized else COLOR_UNKNOWN

        # Draw sleek corner brackets around face
        corner_len = int(min(right - left, bottom - top) * 0.22)
        thickness = 3
        # Top-Left
        cv2.line(img, (left, top), (left + corner_len, top), box_color, thickness)
        cv2.line(img, (left, top), (left, top + corner_len), box_color, thickness)
        # Top-Right
        cv2.line(img, (right, top), (right - corner_len, top), box_color, thickness)
        cv2.line(img, (right, top), (right, top + corner_len), box_color, thickness)
        # Bottom-Left
        cv2.line(img, (left, bottom), (left + corner_len, bottom), box_color, thickness)
        cv2.line(img, (left, bottom), (left, bottom - corner_len), box_color, thickness)
        # Bottom-Right
        cv2.line(img, (right, bottom), (right - corner_len, bottom), box_color, thickness)
        cv2.line(img, (right, bottom), (right, bottom - corner_len), box_color, thickness)

        # Thin enclosing rectangle
        cv2.rectangle(img, (left, top), (right, bottom), box_color, 1)

        # Labels
        if is_recognized:
            title_text = f"{name}"
            sub_text = f"Roll: {roll}"
            if liveness_required:
                liveness_text = "Liveness: Verified" if liveness_ok else "Please Blink to Verify"
                liveness_color = COLOR_RECOGNIZED if liveness_ok else COLOR_WARNING
            else:
                liveness_text = "Verified"
                liveness_color = COLOR_RECOGNIZED
        else:
            title_text = "Unknown Person"
            sub_text = "Not Registered"
            liveness_text = "Access Denied"
            liveness_color = COLOR_UNKNOWN

        # Draw semi-transparent header pill above face
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale_title = 0.55
        font_scale_sub = 0.42

        badge_w = max(right - left, 180)
        badge_h = 58
        b_x1 = left
        b_y1 = max(0, top - badge_h - 8)
        b_x2 = b_x1 + badge_w
        b_y2 = b_y1 + badge_h

        # Semi-transparent dark background for the pill
        overlay = img.copy()
        cv2.rectangle(overlay, (b_x1, b_y1), (b_x2, b_y2), (20, 20, 26), -1)
        cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)

        # Left accent stripe on badge
        cv2.rectangle(img, (b_x1, b_y1), (b_x1 + 4, b_y2), box_color, -1)

        # Draw texts
        cv2.putText(img, title_text, (b_x1 + 10, b_y1 + 18), font, font_scale_title, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(img, sub_text, (b_x1 + 10, b_y1 + 35), font, font_scale_sub, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(img, liveness_text, (b_x1 + 10, b_y1 + 50), font, font_scale_sub, liveness_color, 1, cv2.LINE_AA)
