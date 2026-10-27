import csv
import io
import os
import sqlite3
from datetime import datetime
from functools import wraps
from io import BytesIO

from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, make_response, redirect, render_template,
    request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "development-only-change-this-key")
DB_PATH = os.getenv("DATABASE_PATH", "student_performance.db")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

PASS_MARK = 40
ATTENDANCE_WARNING = 75
GRADE_RULES = [(90, "O"), (80, "A+"), (70, "A"), (60, "B+"), (50, "B"), (0, "F")]


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            register_number TEXT NOT NULL UNIQUE COLLATE NOCASE,
            department TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS semesters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            year TEXT NOT NULL,
            semester TEXT NOT NULL,
            classes_attended INTEGER NOT NULL DEFAULT 0,
            total_classes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(student_id, year, semester)
        );
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semester_id INTEGER NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
            subject TEXT NOT NULL,
            mark REAL NOT NULL CHECK(mark >= 0 AND mark <= 100),
            UNIQUE(semester_id, subject)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            register_number TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if count == 0 and os.getenv("LOAD_SAMPLE_DATA", "true").lower() == "true":
            now = datetime.now().isoformat(timespec="seconds")
            samples = [
                ("Ananya Kumar", "REG2026001", "AI & Data Science", "2026", "1", 44, 48,
                 [("Python", 92), ("Mathematics", 88), ("AI Fundamentals", 95)]),
                ("Ravi Kumar", "REG2026002", "Computer Science", "2026", "1", 35, 48,
                 [("Python", 67), ("Mathematics", 72), ("Database Systems", 59)]),
                ("Meena Devi", "REG2026003", "Information Technology", "2026", "1", 30, 48,
                 [("Python", 32), ("Mathematics", 45), ("Database Systems", 39)]),
            ]
            for name, reg, dept, year, sem, attended, total, subjects in samples:
                cur = db.execute("INSERT INTO students(name,register_number,department,created_at) VALUES(?,?,?,?)",
                                 (name, reg, dept, now))
                sid = cur.lastrowid
                cur = db.execute("""INSERT INTO semesters(student_id,year,semester,classes_attended,total_classes,created_at)
                                    VALUES(?,?,?,?,?,?)""", (sid, year, sem, attended, total, now))
                semid = cur.lastrowid
                db.executemany("INSERT INTO marks(semester_id,subject,mark) VALUES(?,?,?)",
                               [(semid, sub, mark) for sub, mark in subjects])


def log_change(db, student_id, register_number, action, details):
    db.execute("INSERT INTO audit_log(student_id,register_number,action,details,created_at) VALUES(?,?,?,?,?)",
               (student_id, register_number, action, details, datetime.now().isoformat(timespec="seconds")))


def grade_for(avg):
    for minimum, grade in GRADE_RULES:
        if avg >= minimum:
            return grade
    return "F"


def performance_for(avg):
    if avg >= 85:
        return "Excellent"
    if avg >= 50:
        return "Average"
    return "Weak"


def semester_summary(db, sem):
    marks = db.execute("SELECT subject,mark FROM marks WHERE semester_id=? ORDER BY subject", (sem["id"],)).fetchall()
    vals = [float(m["mark"]) for m in marks]
    avg = sum(vals) / len(vals) if vals else 0
    passed = bool(vals) and all(v >= PASS_MARK for v in vals)
    attended, total = sem["classes_attended"], sem["total_classes"]
    attendance = (attended / total * 100) if total else 0
    return {
        "subjects": marks, "total_marks": sum(vals), "subject_count": len(vals),
        "average": avg, "grade": grade_for(avg), "performance": performance_for(avg),
        "passed": passed, "attendance": attendance, "attendance_warning": attendance < ATTENDANCE_WARNING
    }


def student_bundle(db, student_id):
    student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        abort(404)
    semesters = db.execute("SELECT * FROM semesters WHERE student_id=? ORDER BY year, semester", (student_id,)).fetchall()
    results = []
    all_marks = []
    for sem in semesters:
        summary = semester_summary(db, sem)
        results.append({"semester": sem, **summary})
        all_marks.extend(float(m["mark"]) for m in summary["subjects"])
    overall = sum(all_marks) / len(all_marks) if all_marks else 0
    return {"student": student, "semesters": results, "overall_average": overall,
            "overall_grade": grade_for(overall), "overall_performance": performance_for(overall),
            "overall_passed": bool(all_marks) and all(v >= PASS_MARK for v in all_marks),
            "subject_mark_count": len(all_marks)}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {"admin_username": ADMIN_USERNAME}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if not ADMIN_PASSWORD_HASH:
            flash("Admin password hash is not configured. Run setup_windows.bat or follow README instructions.", "error")
        elif username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(request.args.get("next") or url_for("dashboard"))
        else:
            flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    return redirect(url_for("dashboard" if session.get("admin_logged_in") else "login"))


@app.route("/dashboard")
@login_required
def dashboard():
    with connect_db() as db:
        students = db.execute("SELECT * FROM students ORDER BY name").fetchall()
        bundles = [student_bundle(db, s["id"]) for s in students]
        all_marks = []
        passed = failed = excellent = average = weak = warnings = 0
        subject_totals = {}
        grade_counts = {g: 0 for g in ["O", "A+", "A", "B+", "B", "F"]}
        for b in bundles:
            for r in b["semesters"]:
                all_marks.extend(float(m["mark"]) for m in r["subjects"])
                if r["subject_count"]:
                    if r["passed"]: passed += 1
                    else: failed += 1
                    if r["performance"] == "Excellent": excellent += 1
                    elif r["performance"] == "Average": average += 1
                    else: weak += 1
                    grade_counts[r["grade"]] += 1
                    if r["attendance_warning"]: warnings += 1
                    for m in r["subjects"]:
                        sub = m["subject"]
                        subject_totals.setdefault(sub, []).append(float(m["mark"]))
        subject_rows = [{"subject": k, "average": sum(v)/len(v), "count": len(v)}
                        for k, v in sorted(subject_totals.items())]
        total_semesters = sum(len(b["semesters"]) for b in bundles)
        return render_template("dashboard.html", total=len(students), total_semesters=total_semesters,
            passed=passed, failed=failed, excellent=excellent, average=average, weak=weak,
            class_average=sum(all_marks)/len(all_marks) if all_marks else 0,
            warnings=warnings, subject_rows=subject_rows, grade_counts=grade_counts)


@app.route("/students")
@login_required
def students():
    q = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()
    year = request.args.get("year", "").strip()
    grade = request.args.get("grade", "").strip()
    result = request.args.get("result", "").strip()
    performance = request.args.get("performance", "").strip()
    warning = request.args.get("warning", "").strip()
    with connect_db() as db:
        rows = db.execute("SELECT * FROM students ORDER BY name").fetchall()
        departments = [r[0] for r in db.execute("SELECT DISTINCT department FROM students ORDER BY department")]
        all_students = []
        for s in rows:
            bundle = student_bundle(db, s["id"])
            for r in bundle["semesters"]:
                row = {"student": s, "result": r}
                if q and q.lower() not in (s["name"] + " " + s["register_number"]).lower(): continue
                if department and s["department"] != department: continue
                if year and (r["year"] != year and r["semester"] != year): continue
                if grade and r["grade"] != grade: continue
                if result and ("Pass" if r["passed"] else "Fail") != result: continue
                if performance and r["performance"] != performance: continue
                if warning == "yes" and not r["attendance_warning"]: continue
                all_students.append(row)
        return render_template("students.html", rows=all_students, q=q, department=department, year=year,
            grade=grade, result=result, performance=performance, warning=warning, departments=departments)


def validate_student_form(form):
    errors = []
    name = form.get("name", "").strip()
    reg = form.get("register_number", "").strip()
    dept = form.get("department", "").strip()
    if not name: errors.append("Student name is required.")
    if not reg: errors.append("Register number is required.")
    if not dept: errors.append("Department is required.")
    try:
        attended = int(form.get("classes_attended", ""))
        total = int(form.get("total_classes", ""))
        if attended < 0 or total < 0 or attended > total: errors.append("Attendance counts must be non-negative, and attended classes cannot exceed total classes.")
    except ValueError:
        errors.append("Classes attended and total classes must be whole numbers.")
        attended = total = 0
    subjects = []
    names = [x.strip() for x in form.getlist("subject[]")]
    marks = form.getlist("mark[]")
    if len(names) == 0: errors.append("Add at least one subject.")
    if len(names) != len(marks): errors.append("Each subject must have a mark.")
    seen = set()
    for i, sub in enumerate(names):
        if not sub: errors.append(f"Subject {i+1}: name is required."); continue
        if sub.lower() in seen: errors.append(f"Subject {i+1}: duplicate subject name."); continue
        seen.add(sub.lower())
        try:
            mark = float(marks[i])
            if not 0 <= mark <= 100: raise ValueError()
            subjects.append((sub, mark))
        except (ValueError, IndexError):
            errors.append(f"Subject {i+1}: mark must be between 0 and 100.")
    return errors, {"name": name, "register_number": reg, "department": dept,
                    "year": form.get("year", "").strip(), "semester": form.get("semester", "").strip(),
                    "attended": attended, "total": total, "subjects": subjects}


def save_semester(db, student_id, data, semester_id=None):
    now = datetime.now().isoformat(timespec="seconds")
    if semester_id:
        db.execute("""UPDATE semesters SET year=?,semester=?,classes_attended=?,total_classes=? WHERE id=? AND student_id=?""",
                   (data["year"], data["semester"], data["attended"], data["total"], semester_id, student_id))
        db.execute("DELETE FROM marks WHERE semester_id=?", (semester_id,))
        sid = semester_id
    else:
        cur = db.execute("""INSERT INTO semesters(student_id,year,semester,classes_attended,total_classes,created_at)
                            VALUES(?,?,?,?,?,?)""",
                         (student_id, data["year"], data["semester"], data["attended"], data["total"], now))
        sid = cur.lastrowid
    db.executemany("INSERT INTO marks(semester_id,subject,mark) VALUES(?,?,?)",
                   [(sid, subject, mark) for subject, mark in data["subjects"]])
    return sid


@app.route("/students/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        errors, data = validate_student_form(request.form)
        if not data["year"] or not data["semester"]: errors.append("Year and semester are required.")
        with connect_db() as db:
            exists = db.execute("SELECT id FROM students WHERE register_number=? COLLATE NOCASE", (data["register_number"],)).fetchone()
            if exists: errors.append("That register number already exists.")
            if not errors:
                try:
                    cur = db.execute("INSERT INTO students(name,register_number,department,created_at) VALUES(?,?,?,?)",
                                     (data["name"], data["register_number"], data["department"], datetime.now().isoformat(timespec="seconds")))
                    sid = cur.lastrowid
                    save_semester(db, sid, data)
                    log_change(db, sid, data["register_number"], "Student created", f"Created student and semester {data['year']} / {data['semester']}.")
                    flash("Student and semester record added successfully.", "success")
                    return redirect(url_for("student_detail", student_id=sid))
                except sqlite3.IntegrityError as exc:
                    errors.append("Could not save record. Check duplicate register numbers or semester entries.")
        for e in errors: flash(e, "error")
    return render_template("student_form.html", mode="add", student=None, semester=None, marks=[])


@app.route("/students/<int:student_id>")
@login_required
def student_detail(student_id):
    with connect_db() as db:
        bundle = student_bundle(db, student_id)
        audit = db.execute("SELECT * FROM audit_log WHERE student_id=? ORDER BY id DESC LIMIT 30", (student_id,)).fetchall()
        return render_template("student_detail.html", b=bundle, audit=audit)


@app.route("/students/<int:student_id>/semester/add", methods=["GET", "POST"])
@login_required
def add_semester(student_id):
    with connect_db() as db:
        student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        if not student: abort(404)
        if request.method == "POST":
            errors, data = validate_student_form(request.form)
            if not data["year"] or not data["semester"]: errors.append("Year and semester are required.")
            if db.execute("SELECT id FROM semesters WHERE student_id=? AND year=? AND semester=?",
                          (student_id, data["year"], data["semester"])).fetchone():
                errors.append("This student already has a record for that year and semester.")
            if not errors:
                try:
                    save_semester(db, student_id, data)
                    log_change(db, student_id, student["register_number"], "Semester added",
                               f"Added semester {data['year']} / {data['semester']}.")
                    flash("Semester record added.", "success")
                    return redirect(url_for("student_detail", student_id=student_id))
                except sqlite3.IntegrityError:
                    errors.append("Could not save semester. Check subject names and semester details.")
            for e in errors: flash(e, "error")
        return render_template("student_form.html", mode="semester", student=student, semester=None, marks=[])


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    with connect_db() as db:
        student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        if not student: abort(404)
        if request.method == "POST":
            name, reg, dept = (request.form.get(k, "").strip() for k in ("name", "register_number", "department"))
            errors = []
            if not name or not reg or not dept: errors.append("Name, register number, and department are required.")
            other = db.execute("SELECT id FROM students WHERE register_number=? COLLATE NOCASE AND id<>?", (reg, student_id)).fetchone()
            if other: errors.append("That register number is already used by another student.")
            if not errors:
                before = f"name={student['name']}; register={student['register_number']}; department={student['department']}"
                after = f"name={name}; register={reg}; department={dept}"
                db.execute("UPDATE students SET name=?,register_number=?,department=? WHERE id=?", (name, reg, dept, student_id))
                if before != after:
                    log_change(db, student_id, reg, "Student details updated", f"Previous: {before} | Updated: {after}")
                flash("Student details updated.", "success")
                return redirect(url_for("student_detail", student_id=student_id))
            for e in errors: flash(e, "error")
        return render_template("student_edit.html", student=student)


@app.route("/students/<int:student_id>/semester/<int:semester_id>/edit", methods=["GET", "POST"])
@login_required
def edit_semester(student_id, semester_id):
    with connect_db() as db:
        student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        sem = db.execute("SELECT * FROM semesters WHERE id=? AND student_id=?", (semester_id, student_id)).fetchone()
        if not student or not sem: abort(404)
        marks = db.execute("SELECT * FROM marks WHERE semester_id=? ORDER BY id", (semester_id,)).fetchall()
        if request.method == "POST":
            errors, data = validate_student_form(request.form)
            if not data["year"] or not data["semester"]: errors.append("Year and semester are required.")
            dup = db.execute("SELECT id FROM semesters WHERE student_id=? AND year=? AND semester=? AND id<>?",
                             (student_id, data["year"], data["semester"], semester_id)).fetchone()
            if dup: errors.append("This student already has a record for that year and semester.")
            if not errors:
                before = f"year={sem['year']}; semester={sem['semester']}; attendance={sem['classes_attended']}/{sem['total_classes']}; marks=" + ", ".join(f"{m['subject']}:{m['mark']}" for m in marks)
                after = f"year={data['year']}; semester={data['semester']}; attendance={data['attended']}/{data['total']}; marks=" + ", ".join(f"{s}:{m}" for s, m in data["subjects"])
                db.execute("UPDATE semesters SET year=?,semester=?,classes_attended=?,total_classes=? WHERE id=?",
                           (data["year"], data["semester"], data["attended"], data["total"], semester_id))
                db.execute("DELETE FROM marks WHERE semester_id=?", (semester_id,))
                db.executemany("INSERT INTO marks(semester_id,subject,mark) VALUES(?,?,?)",
                               [(semester_id, s, m) for s, m in data["subjects"]])
                log_change(db, student_id, student["register_number"], "Semester/marks updated", f"Previous: {before} | Updated: {after}")
                flash("Semester marks and attendance updated.", "success")
                return redirect(url_for("student_detail", student_id=student_id))
            for e in errors: flash(e, "error")
        return render_template("student_form.html", mode="edit_semester", student=student, semester=sem, marks=marks)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
def delete_student(student_id):
    with connect_db() as db:
        student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        if not student: abort(404)
        reg = student["register_number"]
        log_change(db, student_id, reg, "Student deleted", "Student and associated semester/mark records permanently deleted.")
        # Keep the audit entry by nulling student_id before cascading deletion.
        db.execute("UPDATE audit_log SET student_id=NULL WHERE student_id=?", (student_id,))
        db.execute("DELETE FROM students WHERE id=?", (student_id,))
        flash(f"Student {reg} and associated semester records deleted.", "success")
    return redirect(url_for("students"))


@app.route("/students/export.csv")
@login_required
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student ID", "Name", "Register Number", "Department", "Year", "Semester",
                     "Subject", "Mark", "Total Marks", "Average", "Grade", "Pass/Fail",
                     "Performance Category", "Classes Attended", "Total Classes", "Attendance Percentage"])
    with connect_db() as db:
        for s in db.execute("SELECT * FROM students ORDER BY register_number"):
            for sem in db.execute("SELECT * FROM semesters WHERE student_id=? ORDER BY year,semester", (s["id"],)):
                summary = semester_summary(db, sem)
                for m in summary["subjects"]:
                    writer.writerow([s["id"], s["name"], s["register_number"], s["department"], sem["year"],
                        sem["semester"], m["subject"], m["mark"], summary["total_marks"],
                        f"{summary['average']:.2f}", summary["grade"], "Pass" if summary["passed"] else "Fail",
                        summary["performance"], sem["classes_attended"], sem["total_classes"],
                        f"{summary['attendance']:.2f}"])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=student_performance_export.csv"
    return response


@app.route("/students/<int:student_id>/report")
@login_required
def student_report(student_id):
    with connect_db() as db:
        b = student_bundle(db, student_id)
        return render_template("report.html", b=b, printable=False)


@app.route("/students/<int:student_id>/report.pdf")
@login_required
def student_report_pdf(student_id):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        flash("PDF library is not installed. Run setup_windows.bat again or install requirements.", "error")
        return redirect(url_for("student_detail", student_id=student_id))
    with connect_db() as db:
        b = student_bundle(db, student_id)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("Student Performance Report", styles["Title"]), Spacer(1, 8)]
    s = b["student"]
    story.append(Paragraph(f"<b>Name:</b> {s['name']} &nbsp;&nbsp; <b>Register No:</b> {s['register_number']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Department:</b> {s['department']}", styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Combined average:</b> {b['overall_average']:.2f}% &nbsp; <b>Grade:</b> {b['overall_grade']} &nbsp; <b>Performance:</b> {b['overall_performance']} &nbsp; <b>Overall status:</b> {'Pass' if b['overall_passed'] else 'Fail'}", styles["Normal"]))
    for r in b["semesters"]:
        story.extend([Spacer(1, 12), Paragraph(f"Year {r['semester']['year']} — Semester {r['semester']['semester']}", styles["Heading2"])])
        data = [["Subject", "Mark / 100"]] + [[m["subject"], f"{m['mark']:g}"] for m in r["subjects"]]
        data += [["Total marks", f"{r['total_marks']:g}"], ["Average", f"{r['average']:.2f}%"],
                 ["Grade / Status", f"{r['grade']} / {'Pass' if r['passed'] else 'Fail'}"],
                 ["Performance", r["performance"]],
                 ["Attendance", f"{r['semester']['classes_attended']} / {r['semester']['total_classes']} ({r['attendance']:.2f}%)"]]
        table = Table(data, colWidths=[100*mm, 60*mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e7eef8")),
            ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#cbd5e1")),
            ("PADDING", (0,0), (-1,-1), 6), ("VALIGN", (0,0), (-1,-1), "TOP")
        ]))
        story.append(table)
    doc.build(story)
    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={s['register_number']}_performance_report.pdf"
    return response


@app.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename.lower().endswith(".csv"):
            flash("Choose a .csv file.", "error")
            return redirect(url_for("import_csv"))
        try:
            content = file.stream.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            required = {"name", "register_number", "department", "year", "semester", "subject", "mark",
                        "classes_attended", "total_classes"}
            if not reader.fieldnames or not required.issubset({h.strip().lower() for h in reader.fieldnames}):
                flash("CSV must contain these headers: " + ", ".join(sorted(required)), "error")
                return redirect(url_for("import_csv"))
            # Normalize header names and validate every row before inserting anything.
            rows = []
            errors = []
            seen_regs = {}
            seen_sem_subject = set()
            for line, raw in enumerate(reader, start=2):
                row = {str(k).strip().lower(): (v or "").strip() for k, v in raw.items() if k is not None}
                if not any(row.values()): continue
                missing = [k for k in required if not row.get(k)]
                if missing:
                    errors.append(f"Row {line}: missing {', '.join(sorted(missing))}."); continue
                reg = row["register_number"]
                identity = (row["name"].strip().casefold(), row["department"].strip().casefold())
                if reg.lower() in seen_regs and seen_regs[reg.lower()] != identity:
                    errors.append(f"Row {line}: register number {reg} is associated with different student details in this file.")
                else:
                    seen_regs[reg.lower()] = identity
                try:
                    mark = float(row["mark"])
                    attended, total = int(row["classes_attended"]), int(row["total_classes"])
                    if not 0 <= mark <= 100: raise ValueError("mark must be 0-100")
                    if attended < 0 or total < 0 or attended > total: raise ValueError("invalid attendance counts")
                except ValueError as exc:
                    errors.append(f"Row {line}: {exc}."); continue
                key = (reg.lower(), row["year"], row["semester"], row["subject"].lower())
                if key in seen_sem_subject: errors.append(f"Row {line}: duplicate subject in semester for {reg}.")
                seen_sem_subject.add(key)
                rows.append({**row, "mark_num": mark, "attended_num": attended, "total_num": total, "line": line})
            if not rows and not errors: errors.append("CSV contains no data rows.")
            with connect_db() as db:
                existing = {r[0].lower() for r in db.execute("SELECT register_number FROM students")}
                for row in rows:
                    if row["register_number"].lower() in existing:
                        errors.append(f"Row {row['line']}: register number {row['register_number']} already exists in database.")
                # One consistent attendance pair and department/name per semester/student.
                groupdata = {}
                for row in rows:
                    key = (row["register_number"].lower(), row["year"], row["semester"])
                    values = (row["name"], row["department"], row["attended_num"], row["total_num"])
                    if key in groupdata and groupdata[key] != values:
                        errors.append(f"Row {row['line']}: student details or attendance differ across subjects in the same semester.")
                    groupdata[key] = values
                if errors:
                    return render_template("import.html", errors=errors, preview=rows)
                now = datetime.now().isoformat(timespec="seconds")
                by_reg = {}
                for row in rows: by_reg.setdefault(row["register_number"], []).append(row)
                for reg, items in by_reg.items():
                    first = items[0]
                    cur = db.execute("INSERT INTO students(name,register_number,department,created_at) VALUES(?,?,?,?)",
                                     (first["name"], reg, first["department"], now))
                    sid = cur.lastrowid
                    groups = {}
                    for row in items: groups.setdefault((row["year"], row["semester"]), []).append(row)
                    for (year, semester), group in groups.items():
                        f = group[0]
                        cur = db.execute("INSERT INTO semesters(student_id,year,semester,classes_attended,total_classes,created_at) VALUES(?,?,?,?,?,?)",
                                         (sid, year, semester, f["attended_num"], f["total_num"], now))
                        semid = cur.lastrowid
                        db.executemany("INSERT INTO marks(semester_id,subject,mark) VALUES(?,?,?)",
                                       [(semid, r["subject"], r["mark_num"]) for r in group])
                    log_change(db, sid, reg, "CSV import", f"Imported {len(items)} subject rows.")
            flash(f"Successfully imported {len(by_reg)} students from CSV.", "success")
            return redirect(url_for("students"))
        except (UnicodeDecodeError, csv.Error, sqlite3.IntegrityError, ValueError) as exc:
            flash(f"Could not import CSV: {exc}", "error")
            return redirect(url_for("import_csv"))
    return render_template("import.html", errors=[], preview=[])


@app.route("/audit")
@login_required
def audit():
    with connect_db() as db:
        rows = db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 300").fetchall()
    return render_template("audit.html", rows=rows)


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
