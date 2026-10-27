# AI-Based Rule and Pattern Recognition System
## Student Performance Analysis

A local Flask + SQLite website that analyzes student marks and attendance using fixed, transparent rules. It does not use machine learning or deep learning.

## Features
- Administrator login with password hashing and environment-based configuration.
- Student profile per unique register number and multiple semester records.
- Add/edit students, semesters, dynamic subject marks, and delete confirmation.
- Automatic total, average, grade, pass/fail, performance category, and attendance calculation.
- Dashboard statistic cards and tables (no charts).
- Search and filters for student details, department, year/semester, grade, result, category, and attendance warning.
- CSV import with complete-file validation before any data is saved.
- CSV export of student and semester subject records.
- Individual PDF and printable HTML reports.
- Record change history with timestamps and previous/updated values for edits.
- Sample records load only when the database is empty.

## Requirements
- Windows 10/11
- Python 3.11 or newer (Python 3.12/3.13 recommended)
- Internet connection during first setup to install Python packages

## Installation on Windows
1. Extract the ZIP into a normal folder, for example `C:\StudentPerformanceSystem`.
2. Install Python from https://www.python.org/downloads/ if it is not installed. During installation, enable **Add Python to PATH**.
3. Open the extracted folder.
4. Double-click `setup_windows.bat`.
5. Choose an administrator password when asked (at least 10 characters). The password will not be shown while typing.
6. When Notepad opens `.env`, paste the generated hash after `ADMIN_PASSWORD_HASH=`. Replace `FLASK_SECRET_KEY` with a long random secret. Save and close Notepad.
7. Double-click `run_windows.bat`.
8. Open a browser and visit **http://127.0.0.1:5000**.
9. Sign in with username `admin` (or the username you set in `.env`) and the password you chose.

Keep `.env` private. It is ignored by Git and must not be uploaded to GitHub.

## First run and sample data
Sample data is inserted only if the database is empty and `LOAD_SAMPLE_DATA=true`. If you want an empty database before the first launch, set `LOAD_SAMPLE_DATA=false` in `.env`. Existing data is never reset on later launches.

## CSV import format
Download the sample CSV from the Import CSV page. Required headers are:

`name,register_number,department,year,semester,subject,mark,classes_attended,total_classes`

Use one row per subject. Repeat the student and semester details on each subject row. All subject rows belonging to the same student in the same semester must have the same name, department, and attendance counts. Register numbers must not already exist in the database. If any row is invalid, the entire file is rejected; no rows are saved.

Marks must be between 0 and 100. Attendance values must be whole numbers, and classes attended cannot exceed total classes. CSV import adds new student profiles; use the website to add a semester to an existing profile.

## Fixed rules
- A subject passes at 40/100 or above.
- A semester fails if any subject is below 40.
- Grade: O >=90; A+ >=80; A >=70; B+ >=60; B >=50; F <50.
- Performance category: Excellent >=85; Average >=50 and <85; Weak <50.
- Attendance warning: calculated attendance below 75%.
- Attendance percentage = classes attended / total classes × 100. If total classes is zero, attendance is treated as 0%.
- The combined average is calculated across all recorded subject marks, not by averaging semester averages. Combined status is Fail if any recorded subject mark is below 40.

## GitHub
1. Create a new repository on GitHub.
2. Upload the project source files, but **do not upload `.env`, `.venv`, or `student_performance.db`**.
3. Keep `.gitignore` in the repository.
4. If `.env` is accidentally committed, change the admin password and secret key; deleting the file in a later commit does not erase it from Git history.

## Troubleshooting
- **Python not found:** reinstall Python and enable PATH, then reopen the terminal.
- **Package installation failed:** check internet access and run `setup_windows.bat` again.
- **PDF report error:** run setup again to install ReportLab.
- **Forgot admin password:** run `python make_admin_hash.py` inside the activated virtual environment, replace `ADMIN_PASSWORD_HASH` in `.env`, and restart the website.
- **Database backup:** stop the website and copy `student_performance.db` to a safe location.

## Notes
This is an educational project. Before exposing it to a public network, add production-grade deployment configuration, CSRF protection, rate limiting, backups, and a proper secret-management process. It binds to localhost only by default.
