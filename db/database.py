from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("SMS_V2_DB", DB_DIR / "sms_v2.db"))

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2_sha256${100_000}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return dk.hex() == hash_hex
    except Exception:
        return False


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _seed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    if not cur.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
            ("admin", hash_password("admin123"), "admin"),
        )
    for name in ("Clubhouse", "Gym", "Swimming Pool", "Party Hall"):
        cur.execute("INSERT OR IGNORE INTO amenities (name) VALUES (?)", (name,))


def initialise_database() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _seed(conn)
        conn.commit()
    finally:
        conn.close()


def seed_demo_data() -> None:
    """Populate the database with sample data. Safe to call any number of times:
    it only inserts when no residents exist yet."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if cur.execute("SELECT 1 FROM residents LIMIT 1").fetchone():
            return
        now = now_iso()

        def add_user(username: str, password: str, role: str) -> int:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                (username, hash_password(password), role),
            )
            return cur.lastrowid

        residents = [
            ("aman101", "101", "Aman", "Verma", "101", "981-101", "aman.verma@example.com"),
            ("neha102", "102", "Neha", "Gupta", "102", "981-102", "neha.gupta@example.com"),
            ("rohan201", "201", "Rohan", "Mehta", "201", "981-201", "rohan.mehta@example.com"),
            ("priya301", "301", "Priya", "Nair", "301", "981-301", "priya.nair@example.com"),
            ("suresh302", "302", "Suresh", "Iyer", "302", "981-302", "suresh.iyer@example.com"),
        ]
        resident_ids: dict[str, int] = {}
        for uname, pwd, first, last, flat, phone, email in residents:
            uid = add_user(uname, pwd, "resident")
            cur.execute(
                "INSERT INTO residents (first_name,last_name,flat_no,phone,email,user_id) VALUES (?,?,?,?,?,?)",
                (first, last, flat, phone, email, uid),
            )
            resident_ids[flat] = cur.lastrowid

        staff_flat = [
            ("rajesh", "demo123", "Rajesh", "Kumar"),
            ("meena", "demo123", "Meena", "Das"),
        ]
        staff_ids: dict[str, int] = {}
        for uname, pwd, first, last in staff_flat:
            uid = add_user(uname, pwd, "staff")
            cur.execute(
                "INSERT INTO staff (name, phone, user_id) VALUES (?,?,?)",
                (f"{first} {last}", "", uid),
            )
            staff_ids[first] = cur.lastrowid

        for flat, visitor, purpose in [
            ("102", "Vikram Singh", "Delivery"),
            ("201", "Anita Rao", "Guest"),
            ("301", "Karan Malhotra", "Contractor"),
        ]:
            cur.execute(
                """INSERT INTO visitors (visitor_name, flat_no, phone, vehicle_no, purpose, check_in)
                   VALUES (?,?,?,?,?,?)""",
                (visitor, flat, "9", "DL-AB", purpose, now),
            )
        cur.execute(
            """UPDATE visitors SET check_out=?, phone=?, vehicle_no=? WHERE visitor_name=? AND check_out IS NULL""",
            ("2026-09-28 12:00:00", "9", "DL-CD", "Anita Rao"),
        )

        complaints = [
            ("101", "Plumbing", "Water leaking from bathroom ceiling", "pending", None),
            ("201", "Electrical", "Power socket in the living room is sparking", "in_progress", "Rajesh"),
            ("301", "Cleaning", "Garbage not collected on the 3rd floor", "resolved", None),
            ("301", "Noise", "Loud music after midnight from flat 301", "pending", None),
        ]
        for flat, cat, desc, status, assigned in complaints:
            cur.execute(
                """INSERT INTO complaints (resident_id, category, description, status, assigned_to, created_at, resolved_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    resident_ids[flat],
                    cat,
                    desc,
                    status,
                    staff_ids.get(assigned) if assigned else None,
                    now,
                    now if status == "resolved" else None,
                ),
            )

        cur.execute(
            "INSERT INTO announcements (title, body, posted_by, created_at) VALUES (?,?,?,?)",
            ("Water shutdown on Sunday", "Supply will be off from 9am to 12pm for tank cleaning.", "admin", now),
        )
        cur.execute(
            "INSERT INTO announcements (title, body, posted_by, created_at) VALUES (?,?,?,?)",
            ("Diwali celebration", "Community celebration in the clubhouse on Saturday at 6pm.", "admin", now),
        )
        cur.execute(
            "INSERT INTO announcements (title, body, posted_by, created_at) VALUES (?,?,?,?)",
            ("Pest control", "Pest control spray scheduled for the basement on Wednesday.", "admin", now),
        )

        bills = [
            ("101", "2026-08", 1500, 1),
            ("101", "2026-09", 1800, 0),
            ("102", "2026-08", 1500, 1),
            ("102", "2026-09", 1800, 0),
            ("201", "2026-08", 1500, 1),
            ("201", "2026-09", 1800, 0),
            ("301", "2026-09", 2200, 0),
            ("302", "2026-09", 2200, 0),
        ]
        for flat, month, amount, paid in bills:
            cur.execute(
                """INSERT INTO maintenance (resident_id, month, amount, paid, paid_at)
                   VALUES (?,?,?,?,?)""",
                (resident_ids[flat], month, amount, paid, "2026-08-10 10:00:00" if paid else None),
            )

        bookings = [
            (1, "101", "2026-10-03", "Evening", "confirmed"),
            (2, "102", "2026-10-05", "Morning", "pending"),
            (3, "201", "2026-10-08", "Evening", "cancelled"),
            (4, "301", "2026-10-10", "Afternoon", "confirmed"),
        ]
        for amenity_id, flat, date, slot, status in bookings:
            cur.execute(
                """INSERT INTO amenity_bookings (amenity_id, resident_id, booking_date, slot, status, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (amenity_id, resident_ids[flat], date, slot, status, now),
            )

        parking = [
            ("P-01", "101", "DL-01-AB"),
            ("P-02", "102", "DL-02-CD"),
            ("P-03", "201", "DL-03-EF"),
        ]
        for slot_no, flat, vehicle in parking:
            cur.execute(
                "INSERT INTO parking_slots (slot_no, resident_id, vehicle_no) VALUES (?,?,?)",
                (slot_no, resident_ids[flat], vehicle),
            )

        conn.commit()
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (username,)
        ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        return dict(row)
    finally:
        conn.close()


def build_session(user: dict) -> dict:
    session = dict(user)
    conn = get_connection()
    try:
        if session["role"] == "resident":
            row = conn.execute(
                "SELECT resident_id, first_name, last_name, flat_no FROM residents WHERE user_id=?",
                (session["user_id"],),
            ).fetchone()
            session["resident_id"] = row["resident_id"] if row else None
            session["flat_no"] = row["flat_no"] if row else None
            session["display_name"] = (
                f"{row['first_name']} {row['last_name']}" if row else session["username"]
            )
        elif session["role"] == "staff":
            row = conn.execute(
                "SELECT staff_id, name FROM staff WHERE user_id=?",
                (session["user_id"],),
            ).fetchone()
            session["staff_id"] = row["staff_id"] if row else None
            session["display_name"] = row["name"] if row else session["username"]
        else:
            session["display_name"] = "Administrator"
    finally:
        conn.close()
    return session


def change_password(user_id: int, new_password: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE user_id=?",
            (hash_password(new_password), user_id),
        )
        conn.commit()
    finally:
        conn.close()