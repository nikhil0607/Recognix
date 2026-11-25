"""
excel_manager.py
Handles all local Excel data persistence for AttendIQ.
Uses Pandas and OpenPyXL to create, format, read, and write:
- data/students.xlsx
- data/attendance.xlsx
"""

import os
from datetime import datetime
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STUDENTS_FILE = os.path.join(DATA_DIR, "students.xlsx")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance.xlsx")

STUDENT_COLUMNS = [
    "Roll Number",
    "Name",
    "Course",
    "Section",
    "Registration Date",
    "Face ID"
]

ATTENDANCE_COLUMNS = [
    "Roll Number",
    "Student Name",
    "Date",
    "Time",
    "Status"
]


def ensure_directories():
    """Ensure data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _apply_excel_styling(filepath: str, sheet_name: str = None):
    """
    Applies clean, professional styling to an Excel workbook using OpenPyXL:
    - Elegant dark-indigo header row with white bold text
    - Subtle zebra striping for rows
    - Thin borders and aligned cells
    - Auto-adjusted column widths
    """
    if not os.path.exists(filepath):
        return

    try:
        wb = openpyxl.load_workbook(filepath)
        ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="312E81", end_color="312E81", fill_type="solid")  # Indigo 900
        data_font = Font(name="Segoe UI", size=10)
        
        even_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        odd_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")

        max_r = ws.max_row
        max_c = ws.max_column

        # Format header row
        ws.row_dimensions[1].height = 28
        for col_num in range(1, max_c + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border

        # Format data rows if any exist
        if max_r > 1:
            for row_num in range(2, max_r + 1):
                fill = even_fill if row_num % 2 == 0 else odd_fill
                ws.row_dimensions[row_num].height = 22
                for col_num in range(1, max_c + 1):
                    cell = ws.cell(row=row_num, column=col_num)
                    cell.font = data_font
                    cell.fill = fill
                    cell.border = thin_border
                    if col_num in [1, 3, 4, 5]:
                        cell.alignment = align_center
                    else:
                        cell.alignment = align_left

        # Adjust column widths safely
        for col_idx in range(1, max_c + 1):
            col_letter = get_column_letter(col_idx)
            max_len = 0
            for row_idx in range(1, max_r + 1):
                val = str(ws.cell(row=row_idx, column=col_idx).value or "")
                if len(val) > max_len:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(max_len + 5, 14)

        wb.save(filepath)
        wb.close()
    except Exception as e:
        print(f"[ExcelManager] Error applying styles to {filepath}: {e}")


def init_excel_files():
    """Initializes students.xlsx and attendance.xlsx if they do not exist."""
    ensure_directories()

    if not os.path.exists(STUDENTS_FILE):
        df_students = pd.DataFrame(columns=STUDENT_COLUMNS)
        df_students.to_excel(STUDENTS_FILE, index=False, engine="openpyxl")
        _apply_excel_styling(STUDENTS_FILE)

    if not os.path.exists(ATTENDANCE_FILE):
        df_attendance = pd.DataFrame(columns=ATTENDANCE_COLUMNS)
        df_attendance.to_excel(ATTENDANCE_FILE, index=False, engine="openpyxl")
        _apply_excel_styling(ATTENDANCE_FILE)


def get_all_students() -> pd.DataFrame:
    """Returns a DataFrame of all registered students."""
    init_excel_files()
    try:
        df = pd.read_excel(STUDENTS_FILE, dtype={"Roll Number": str, "Face ID": str})
        return df.fillna("")
    except Exception as e:
        print(f"[ExcelManager] Error reading students: {e}")
        return pd.DataFrame(columns=STUDENT_COLUMNS)


def get_student_by_roll(roll_number: str) -> dict | None:
    """Finds a student by their unique roll number."""
    df = get_all_students()
    match = df[df["Roll Number"].astype(str).str.strip().str.lower() == str(roll_number).strip().lower()]
    if not match.empty:
        return match.iloc[0].to_dict()
    return None


def register_student(roll_number: str, name: str, course: str, section: str, face_id: str) -> tuple[bool, str]:
    """
    Registers a new student into students.xlsx.
    Enforces uniqueness of roll numbers.
    """
    init_excel_files()
    roll_number = str(roll_number).strip()
    name = str(name).strip()
    course = str(course).strip()
    section = str(section).strip()
    face_id = str(face_id).strip()

    if not roll_number or not name:
        return False, "Roll number and Name cannot be empty."

    df = get_all_students()
    if not df.empty:
        existing = df[df["Roll Number"].astype(str).str.strip().str.lower() == roll_number.lower()]
        if not existing.empty:
            return False, f"Student with Roll Number '{roll_number}' is already registered."

    reg_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = {
        "Roll Number": roll_number,
        "Name": name,
        "Course": course,
        "Section": section,
        "Registration Date": reg_date,
        "Face ID": face_id
    }

    try:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(STUDENTS_FILE, index=False, engine="openpyxl")
        _apply_excel_styling(STUDENTS_FILE)
        return True, "Student registered successfully."
    except Exception as e:
        return False, f"Failed to save student record: {e}"


def delete_student(roll_number: str) -> tuple[bool, str, str | None]:
    """
    Deletes a student by roll number from students.xlsx.
    Returns (success, message, face_id).
    Historical attendance records are preserved.
    """
    init_excel_files()
    roll_number = str(roll_number).strip()
    df = get_all_students()

    if df.empty:
        return False, "No students registered.", None

    idx = df[df["Roll Number"].astype(str).str.strip().str.lower() == roll_number.lower()].index
    if idx.empty:
        return False, f"Student with Roll Number '{roll_number}' not found.", None

    face_id = str(df.loc[idx[0], "Face ID"])
    df = df.drop(idx).reset_index(drop=True)

    try:
        df.to_excel(STUDENTS_FILE, index=False, engine="openpyxl")
        _apply_excel_styling(STUDENTS_FILE)
        return True, f"Student {roll_number} deleted successfully.", face_id
    except Exception as e:
        return False, f"Failed to delete student: {e}", None


def get_all_attendance() -> pd.DataFrame:
    """Returns all attendance records."""
    init_excel_files()
    try:
        df = pd.read_excel(ATTENDANCE_FILE, dtype={"Roll Number": str})
        return df.fillna("")
    except Exception as e:
        print(f"[ExcelManager] Error reading attendance: {e}")
        return pd.DataFrame(columns=ATTENDANCE_COLUMNS)


def get_today_attendance() -> pd.DataFrame:
    """Returns today's attendance records."""
    df = get_all_attendance()
    if df.empty:
        return df
    today_str = datetime.now().strftime("%Y-%m-%d")
    return df[df["Date"].astype(str).str.strip() == today_str]


def has_marked_today(roll_number: str) -> bool:
    """Checks whether the student has already marked attendance today."""
    df_today = get_today_attendance()
    if df_today.empty:
        return False
    match = df_today[df_today["Roll Number"].astype(str).str.strip().str.lower() == str(roll_number).strip().lower()]
    return not match.empty


def mark_attendance(roll_number: str, student_name: str, status: str = "Present") -> tuple[bool, str]:
    """
    Marks attendance in attendance.xlsx.
    Prevents duplicate entries on the same calendar day.
    """
    init_excel_files()
    roll_number = str(roll_number).strip()
    student_name = str(student_name).strip()
    status = str(status).strip()

    if has_marked_today(roll_number):
        return False, f"Attendance already marked today for {student_name} ({roll_number})."

    now = datetime.now()
    today_date = now.strftime("%Y-%m-%d")
    curr_time = now.strftime("%I:%M:%S %p")

    new_row = {
        "Roll Number": roll_number,
        "Student Name": student_name,
        "Date": today_date,
        "Time": curr_time,
        "Status": status
    }

    try:
        df = get_all_attendance()
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(ATTENDANCE_FILE, index=False, engine="openpyxl")
        _apply_excel_styling(ATTENDANCE_FILE)
        return True, f"Attendance marked for {student_name} [{status}]."
    except Exception as e:
        return False, f"Failed to record attendance: {e}"


def get_student_attendance_stats(roll_number: str) -> dict:
    """
    Calculates total unique attendance days, student's presence/late counts,
    and attendance percentage.
    """
    roll_number = str(roll_number).strip().lower()
    df_all = get_all_attendance()
    if df_all.empty:
        return {"total_sessions": 0, "attended": 0, "present": 0, "late": 0, "percentage": 0.0}

    unique_dates = df_all["Date"].nunique()
    student_records = df_all[df_all["Roll Number"].astype(str).str.strip().str.lower() == roll_number]

    attended = len(student_records)
    present_cnt = len(student_records[student_records["Status"].str.lower() == "present"])
    late_cnt = len(student_records[student_records["Status"].str.lower() == "late"])

    percentage = round((attended / unique_dates * 100), 1) if unique_dates > 0 else 0.0

    return {
        "total_sessions": unique_dates,
        "attended": attended,
        "present": present_cnt,
        "late": late_cnt,
        "percentage": percentage
    }


def get_dashboard_stats() -> dict:
    """Returns summary stats for the Home page dashboard."""
    students_df = get_all_students()
    today_df = get_today_attendance()

    total_students = len(students_df)
    today_present = len(today_df[today_df["Status"].astype(str).str.lower() == "present"])
    today_late = len(today_df[today_df["Status"].astype(str).str.lower() == "late"])

    # Recent attendance items (latest 8)
    recent_records = []
    if not today_df.empty:
        for _, row in today_df.tail(8).iloc[::-1].iterrows():
            recent_records.append({
                "roll": str(row.get("Roll Number", "")),
                "name": str(row.get("Student Name", "")),
                "time": str(row.get("Time", "")),
                "status": str(row.get("Status", "Present"))
            })

    return {
        "total_students": total_students,
        "today_present": today_present,
        "today_late": today_late,
        "recent_records": recent_records
    }


def export_attendance_report(output_path: str, filter_date: str = None, filter_roll: str = None, filter_status: str = None) -> tuple[bool, str]:
    """
    Exports filtered attendance records to a designated Excel file with styling.
    """
    try:
        df = get_all_attendance()
        if df.empty:
            return False, "No attendance records to export."

        if filter_date and filter_date.strip():
            df = df[df["Date"].astype(str).str.strip() == filter_date.strip()]

        if filter_roll and filter_roll.strip():
            df = df[df["Roll Number"].astype(str).str.strip().str.lower() == filter_roll.strip().lower()]

        if filter_status and filter_status.strip() and filter_status != "All":
            df = df[df["Status"].astype(str).str.strip().str.lower() == filter_status.strip().lower()]

        if df.empty:
            return False, "No records matched the selected filters."

        # Ensure directory exists
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        df.to_excel(output_path, index=False, engine="openpyxl")
        _apply_excel_styling(output_path)
        return True, f"Successfully exported {len(df)} records to:\n{output_path}"
    except Exception as e:
        return False, f"Failed to export report: {e}"
