# AttendIQ – Smart Facial Recognition Attendance System

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-CustomTkinter-6366F1.svg)](https://customtkinter.tomschimansky.com/)
[![Biometrics](https://img.shields.io/badge/AI-face__recognition%20%7C%20OpenCV-10B981.svg)](https://github.com/ageitgey/face_recognition)
[![Storage](https://img.shields.io/badge/Storage-Local%20Excel%20(.xlsx)-059669.svg)](https://openpyxl.readthedocs.io/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-gray.svg)]()

**AttendIQ** is a lightweight, fully offline desktop application that automates student and employee attendance through real-time facial recognition and blink-based liveness verification. Built with a dark UI using **CustomTkinter**, AttendIQ requires **no external database, no cloud APIs, and no internet access**—all records are maintained in cleanly styled, human-readable local Excel (`.xlsx`) spreadsheets.

---

## 🌟 Key Features

- **⚡ Real-Time Face Recognition**: Detects and recognizes registered faces with high accuracy using deep 128-dimensional biometric embeddings.
- **👁️ Anti-Spoofing Blink Liveness Detection**: Employs 68-point facial landmark tracking to compute Eye Aspect Ratio (EAR), prompting the individual to blink before recording attendance to mitigate static photo spoofing.
- **📊 100% Local Excel Storage**:
  - `data/students.xlsx`: Student profiles, registration timestamps, and biometric references.
  - `data/attendance.xlsx`: Timestamped logs with status (`Present` or `Late`).
  - No SQL servers, SQLite, Firebase, or cloud dependencies.
- **⏰ Smart Late Entry Detection**: Configurable class start time (e.g., `09:00 AM`). Automated status assignment (`Present` if on time, `Late` after start time).
- **🛡️ Duplicate Prevention**: Strictly enforces one attendance log per student per calendar day.
- **🎨 Modern Dark UI/UX**: CustomTkinter design featuring rounded cards, electric violet accents, floating toast notifications, and responsive layout.
- **📸 Multi-Angle Enrollment**: Captures 5 face samples from varied angles during registration to generate a resilient averaged facial vector.
- **📑 Search, Filter & Excel Export**: Filter logs by student name, roll number, date, or status (`Present`/`Late`), and export custom reports to formatted Excel files.
- **🔊 Audio Feedback**: Plays pleasant confirmation audio tones on successful attendance marking.

---

## 📁 Project Structure

```
AttendIQ/
│
├── main.py                    # Main GUI application & page controllers
├── face_engine.py             # Face detection, 128-d encodings & blink liveness engine
├── attendance.py              # Attendance business logic, class timings & audio feedback
├── excel_manager.py           # Pandas + OpenPyXL Excel database operations & styling
├── requirements.txt           # Project dependencies
├── README.md                  # Complete documentation
│
├── data/
│   ├── students.xlsx          # Registered student records
│   └── attendance.xlsx        # Daily attendance logs
│
├── face_data/
│   └── registered_faces/      # Stored face images (.jpg) and encodings (.npy)
│
└── assets/
    └── logo.png               # AttendIQ biometric application logo
```

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Programming Language** | Python 3.10 - 3.12 | Core application logic |
| **Desktop GUI** | CustomTkinter | Modern dark desktop interface |
| **Computer Vision** | OpenCV (`cv2`) | Webcam capture, video feed & HUD overlay |
| **Biometric AI** | `face_recognition` | HOG face detection & 128-d encodings |
| **Landmark Tracking** | `dlib` (via `face_recognition`) | 68-point landmarks for blink EAR liveness |
| **Data Management** | Pandas & OpenPyXL | Excel spreadsheet reading, writing & styling |
| **Image Processing** | Pillow (PIL) & NumPy | Array manipulations & UI image rendering |

---

## 🚀 Installation & Setup

### 1. Clone or Open the Project
Open a terminal in the project directory:
```bash
cd "path/to/AttendIQ"
```

### 2. Set Up a Virtual Environment (Recommended)
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate
```

### 3. Install Dependencies

#### On Windows:
```bash
# Install precompiled wheels and dependencies
python -m pip install -r requirements.txt
```

> **Note for Windows users**: To prevent CMake build errors for `dlib`, the project uses `dlib-bin`, which installs a precompiled C++ wheel. If installing manually:
> ```bash
> pip install dlib-bin
> pip install face-recognition --no-deps
> pip install face-recognition-models --no-deps
> pip install customtkinter opencv-python pandas openpyxl Pillow "setuptools<70"
> ```

#### On macOS / Linux:
```bash
# Ensure cmake and build tools are installed:
# Ubuntu/Debian: sudo apt-get install cmake build-essential
# macOS: brew install cmake
python -m pip install -r requirements.txt
```

---

## 🖥️ Running AttendIQ

Launch the desktop application with:

```bash
python main.py
```

---

## 📖 Application Walkthrough

### 1. 🏠 Home Page
- **Live Clock & Date**: Displays the current local date and live ticking digital clock.
- **Metric Cards**: Real-time counters for Total Registered Students, Today's Present, and Today's Late count.
- **Live Attendance Feed**: Quick view of recent attendees today.
- **Start Attendance**: One-click shortcut to launch the camera feed.

### 2. 📷 Mark Attendance (Core Workflow)
1. Navigate to **Mark Attendance** from the sidebar.
2. Click **Start Camera**.
3. Position your face within the camera view:
   - **Green bounding box** appears for registered students with their name and roll number.
   - **Orange/Red bounding box** appears for unregistered faces (`Unknown Person`).
4. **Liveness Check**: If liveness is enabled in Settings, the prompt will display *"Please Blink to Verify"*. Once the user blinks, the system verifies liveness and marks attendance.
5. A green toast notification and confirmation chime confirm that attendance is recorded in `data/attendance.xlsx`.
6. Subsequent scans of the same person on the same day display a warning toast indicating attendance has already been recorded today.

### 3. 👤+ Register Student
1. Enter the student's **Roll Number / ID**, **Full Name**, **Course / Department**, and **Section**.
2. Click **Capture & Register Face**.
3. Look directly at the webcam. The system captures **5 multi-angle face samples** (0.6s intervals), computing and averaging the 128-d vectors into a clean `.npy` signature.
4. The student record is saved in `data/students.xlsx`, and their face photo is stored in `face_data/registered_faces/`.

### 4. 👥 Students Directory
- Browse all registered students.
- Search dynamically by student name or roll number.
- Click **View Photo & Stats** to view the student's saved biometric photo, department, and overall attendance percentage.
- Click **Delete Student** to remove a student and their face data while safely preserving historical attendance records.

### 5. 📊 Attendance Logs & Excel Export
- View all historical records with columns: Roll Number, Name, Date, Time, Status.
- Filter records dynamically by keyword, specific date (`YYYY-MM-DD`), or status (`Present`/`Late`).
- Click **Export to Excel** to save the formatted report to any local destination.

### 6. ⚙️ Settings
- **Class Start Time**: Set the cutoff time for on-time arrivals (e.g., `09:00 AM`).
- **Recognition Confidence**: Adjust tolerance threshold between `0.35` (strictest) and `0.65` (looser). Default: `0.50`.
- **Webcam Selection**: Switch between built-in webcam (index 0) and external USB cameras (index 1 or 2).
- **Sound Toggle**: Enable or disable audio chime on attendance.
- **Liveness Toggle**: Enable or disable blink verification.
- **Export Directory**: Choose the default folder for exported spreadsheets.

---

## 🔒 Security & Privacy

- **No Cloud Transmission**: Facial data never leaves your computer.
- **Local Encodings**: Biometric signatures are stored locally as raw 128-dimensional floating point vectors in `face_data/registered_faces/*.npy`.
- **Data Integrity**: Attendance files use safe atomic operations with OpenPyXL, ensuring no accidental record overwrites.

---

## 📄 License
This project is open-source and free to use for academic, commercial, and personal attendance tracking projects.
