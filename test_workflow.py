"""
test_workflow.py - End-to-end integration and functionality test for AttendIQ.
"""

import os
import sys
import time
import numpy as np
import cv2

import excel_manager
from attendance import AttendanceManager
from face_engine import FaceEngine

def run_integration_tests():
    print("=" * 60)
    print("STARTING ATTENDIQ END-TO-END INTEGRATION TEST")
    print("=" * 60)

    # 1. Initialize Excel Files
    print("[1/7] Testing Excel Initialization...")
    excel_manager.init_excel_files()
    assert os.path.exists(excel_manager.STUDENTS_FILE), "students.xlsx not found!"
    assert os.path.exists(excel_manager.ATTENDANCE_FILE), "attendance.xlsx not found!"
    print("   ✔ Excel files initialized.")

    # 2. Test Attendance Logic & Settings
    print("[2/7] Testing AttendanceManager & Config...")
    att_mgr = AttendanceManager()
    assert "class_start_time" in att_mgr.settings
    is_late = att_mgr.is_late()
    print(f"   ✔ Config loaded. Current time evaluation (is_late): {is_late}")

    # 3. Test Student Registration (Synthetic Face Encodings)
    print("[3/7] Testing Face Enrollment & Persistence...")
    face_engine = FaceEngine(tolerance=0.50)

    # Create dummy 128-d face embedding to test enrollment
    test_roll = "TEST-2026-999"
    test_name = "Jane Doe"
    test_course = "Artificial Intelligence"
    test_sec = "AI-1"

    # Generate synthetic face images with valid color space
    dummy_frame = np.zeros((300, 300, 3), dtype=np.uint8)
    dummy_frame[:] = (50, 50, 50)
    # Draw simple facial feature indicators
    cv2.circle(dummy_frame, (150, 150), 80, (200, 200, 200), -1)

    # Save a direct encoding to test face matching directly
    test_face_id = f"{test_roll}_{int(time.time())}"
    synthetic_encoding = np.random.randn(128).astype(np.float64)
    synthetic_encoding /= np.linalg.norm(synthetic_encoding)

    import face_engine as fe_mod
    npy_path = os.path.join(fe_mod.REGISTERED_FACES_DIR, f"{test_face_id}.npy")
    jpg_path = os.path.join(fe_mod.REGISTERED_FACES_DIR, f"{test_face_id}.jpg")
    np.save(npy_path, synthetic_encoding)
    cv2.imwrite(jpg_path, dummy_frame)

    reg_ok, reg_msg = excel_manager.register_student(test_roll, test_name, test_course, test_sec, test_face_id)
    assert reg_ok, f"Student registration failed: {reg_msg}"
    print(f"   ✔ Student registered in Excel: {test_name} ({test_roll})")

    # Duplicate roll test
    dup_ok, dup_msg = excel_manager.register_student(test_roll, "Duplicate Person", "CS", "A", "dummy_fid")
    assert not dup_ok, "Duplicate roll number check failed to block!"
    print(f"   ✔ Duplicate roll successfully blocked: {dup_msg}")

    # Reload engine faces
    face_engine.reload_faces()
    assert test_roll in face_engine.known_rolls, "Engine failed to reload enrolled student!"
    print(f"   ✔ FaceEngine in-memory cache synchronized ({len(face_engine.known_encodings)} faces loaded).")

    # 4. Test Attendance Marking & Duplicate Prevention
    print("[4/7] Testing Attendance Marking & Duplicate Prevention...")
    mark_ok, mark_msg, status = att_mgr.mark_student_attendance(test_roll, test_name)
    assert mark_ok, f"Attendance marking failed: {mark_msg}"
    print(f"   ✔ Attendance marked: {status} ({mark_msg})")

    # Second mark attempt on same day must be rejected
    dup_mark_ok, dup_mark_msg, dup_status = att_mgr.mark_student_attendance(test_roll, test_name)
    assert not dup_mark_ok, "Duplicate attendance on same day was NOT blocked!"
    assert dup_status == "Already Marked"
    print(f"   ✔ Daily duplicate attendance correctly blocked: {dup_mark_msg}")

    # 5. Test Attendance Stats & Dashboard Calculation
    print("[5/7] Testing Stats & Analytics...")
    stats = excel_manager.get_student_attendance_stats(test_roll)
    assert stats["attended"] >= 1, "Stats did not count attended session!"
    dash_stats = excel_manager.get_dashboard_stats()
    assert dash_stats["total_students"] >= 1, "Dashboard failed to count registered student!"
    print(f"   ✔ Student Stats: Attended={stats['attended']}, Pct={stats['percentage']}%")
    print(f"   ✔ Dashboard Stats: Total Students={dash_stats['total_students']}, Today Present={dash_stats['today_present']}, Late={dash_stats['today_late']}")

    # 6. Test Excel Export
    print("[6/7] Testing Excel Report Export...")
    export_target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "test_export.xlsx")
    exp_ok, exp_msg = excel_manager.export_attendance_report(export_target)
    assert exp_ok, f"Export failed: {exp_msg}"
    assert os.path.exists(export_target), "Export file was not written!"
    print(f"   ✔ Attendance report exported successfully to: {export_target}")
    if os.path.exists(export_target):
        os.remove(export_target)

    # 7. Test Student Deletion & Facial Cleanup
    print("[7/7] Testing Student Deletion & Data Preservation...")
    del_ok, del_msg, fid = excel_manager.delete_student(test_roll)
    assert del_ok, f"Delete failed: {del_msg}"
    face_engine.delete_face_data(fid)
    assert not os.path.exists(npy_path), "NPY file was not removed!"
    assert not os.path.exists(jpg_path), "JPG face image was not removed!"

    # Verify historical attendance is still preserved
    hist_df = excel_manager.get_all_attendance()
    assert not hist_df[hist_df["Roll Number"] == test_roll].empty, "Historical attendance was mistakenly wiped!"
    print(f"   ✔ Student deleted from student registry. Biometric files cleared.")
    print(f"   ✔ Historical attendance log safely preserved in attendance.xlsx.")

    print("=" * 60)
    print("ALL 7 INTEGRATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    run_integration_tests()
