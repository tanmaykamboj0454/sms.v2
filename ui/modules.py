from __future__ import annotations

import sqlite3

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, Static

from db.database import (
    change_password,
    get_connection,
    hash_password,
    now_iso,
)
from ui.widgets import CrudView, FieldSpec, FormModal


# ---- shared option builders -------------------------------------------------
def _resident_options() -> list[tuple[str, str]]:
    conn = get_connection()
    try:
        return [
            (f"{r['first_name']} {r['last_name']} ({r['flat_no']})", str(r["resident_id"]))
            for r in conn.execute(
                "SELECT resident_id, first_name, last_name, flat_no FROM residents ORDER BY flat_no"
            )
        ]
    finally:
        conn.close()


def _staff_options() -> list[tuple[str, str]]:
    conn = get_connection()
    try:
        return [
            (s["name"], str(s["staff_id"]))
            for s in conn.execute("SELECT staff_id, name FROM staff ORDER BY name")
        ]
    finally:
        conn.close()


def _amenity_options() -> list[tuple[str, str]]:
    conn = get_connection()
    try:
        return [
            (a["name"], str(a["amenity_id"]))
            for a in conn.execute("SELECT amenity_id, name FROM amenities ORDER BY name")
        ]
    finally:
        conn.close()


# ---- residents ----------------------------------------------------------------
class ResidentsView(CrudView):
    title = "Residents"
    headers = ["ID", "First", "Last", "Flat", "Phone", "Email", "Login"]
    select_sql = """
        SELECT r.resident_id, r.first_name, r.last_name, r.flat_no, r.phone,
               r.email, COALESCE(u.username, '-')
        FROM residents r
        LEFT JOIN users u ON u.user_id = r.user_id
    """
    order_by_sql = "ORDER BY r.flat_no"
    search_cols = ["r.first_name", "r.last_name", "r.flat_no", "r.phone", "COALESCE(u.username,'')"]

    def _apply_role_permissions(self) -> None:
        if self.role != "admin":
            self.can_add = self.can_edit = self.can_delete = False

    def get_form_fields(self) -> list[FieldSpec]:
        return [
            {"name": "first_name", "label": "First Name", "required": True},
            {"name": "last_name", "label": "Last Name", "required": True},
            {"name": "flat_no", "label": "Flat No", "required": True},
            {"name": "phone", "label": "Phone"},
            {"name": "email", "label": "Email"},
            {"name": "username", "label": "Login Username (blank = flat no)"},
            {"name": "password", "label": "Password (blank = flat no)", "type": "password"},
        ]

    def get_edit_values(self, pk) -> dict:
        conn = get_connection()
        try:
            row = conn.execute(
                """SELECT r.first_name, r.last_name, r.flat_no, r.phone, r.email,
                          COALESCE(u.username, '')
                   FROM residents r
                   LEFT JOIN users u ON u.user_id = r.user_id
                   WHERE r.resident_id = ?""",
                (pk,),
            ).fetchone()
            if not row:
                return {}
            return {
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "flat_no": row["flat_no"],
                "phone": row["phone"],
                "email": row["email"],
                "username": row[5],
                "password": "",
            }
        finally:
            conn.close()

    def insert_row(self, data: dict) -> None:
        uname = (data.get("username") or data["flat_no"]).strip()
        pwd = data.get("password") or data["flat_no"]
        conn = get_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                    (uname, hash_password(pwd), "resident"),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Username '{uname}' is already taken.") from exc
            uid = cur.lastrowid
            cur.execute(
                "INSERT INTO residents (first_name,last_name,flat_no,phone,email,user_id) VALUES (?,?,?,?,?,?)",
                (data["first_name"], data["last_name"], data["flat_no"], data.get("phone", ""), data.get("email", ""), uid),
            )
            conn.commit()
        finally:
            conn.close()

    def update_row(self, pk, data: dict) -> None:
        uname = (data.get("username") or data["flat_no"]).strip()
        pwd = data.get("password") or None
        conn = get_connection()
        try:
            cur = conn.cursor()
            row = cur.execute("SELECT user_id FROM residents WHERE resident_id=?", (pk,)).fetchone()
            cur.execute(
                "UPDATE residents SET first_name=?, last_name=?, flat_no=?, phone=?, email=? WHERE resident_id=?",
                (data["first_name"], data["last_name"], data["flat_no"], data.get("phone", ""), data.get("email", ""), pk),
            )
            try:
                if row and row["user_id"]:
                    cur.execute("UPDATE users SET username=? WHERE user_id=?", (uname, row["user_id"]))
                    if pwd:
                        cur.execute(
                            "UPDATE users SET password_hash=? WHERE user_id=?",
                            (hash_password(pwd), row["user_id"]),
                        )
                else:
                    cur.execute(
                        "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                        (uname, hash_password(pwd or data["flat_no"]), "resident"),
                    )
                    new_uid = cur.lastrowid
                    cur.execute("UPDATE residents SET user_id=? WHERE resident_id=?", (new_uid, pk))
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Username '{uname}' is already taken.") from exc
            conn.commit()
        finally:
            conn.close()

    def delete_row(self, pk) -> None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            row = cur.execute("SELECT user_id FROM residents WHERE resident_id=?", (pk,)).fetchone()
            cur.execute("DELETE FROM residents WHERE resident_id=?", (pk,))
            if row and row["user_id"]:
                cur.execute("DELETE FROM users WHERE user_id=?", (row["user_id"],))
            conn.commit()
        finally:
            conn.close()


# ---- security staff ------------------------------------------------------------
class SecurityView(CrudView):
    title = "Security Staff"
    headers = ["ID", "Name", "Phone", "Username"]
    select_sql = """
        SELECT s.staff_id, s.name, s.phone, COALESCE(u.username, '-')
        FROM staff s
        LEFT JOIN users u ON u.user_id = s.user_id
    """
    order_by_sql = "ORDER BY s.name"
    search_cols = ["s.name", "s.phone", "COALESCE(u.username,'')"]

    def _apply_role_permissions(self) -> None:
        if self.role != "admin":
            self.can_add = self.can_edit = self.can_delete = False

    def get_form_fields(self) -> list[FieldSpec]:
        return [
            {"name": "name", "label": "Full Name", "required": True},
            {"name": "phone", "label": "Phone"},
            {"name": "username", "label": "Login Username (blank = name)", "required": True},
            {"name": "password", "label": "Password (blank = username)", "type": "password"},
        ]

    def get_edit_values(self, pk) -> dict:
        conn = get_connection()
        try:
            row = conn.execute(
                """SELECT s.name, s.phone, COALESCE(u.username, '')
                   FROM staff s
                   LEFT JOIN users u ON u.user_id = s.user_id
                   WHERE s.staff_id = ?""",
                (pk,),
            ).fetchone()
            if not row:
                return {}
            return {"name": row["name"], "phone": row["phone"], "username": row[2], "password": ""}
        finally:
            conn.close()

    def insert_row(self, data: dict) -> None:
        uname = (data.get("username") or data["name"]).strip()
        pwd = data.get("password") or uname
        conn = get_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                    (uname, hash_password(pwd), "staff"),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Username '{uname}' is already taken.") from exc
            uid = cur.lastrowid
            cur.execute(
                "INSERT INTO staff (name, phone, user_id) VALUES (?,?,?)",
                (data["name"], data.get("phone", ""), uid),
            )
            conn.commit()
        finally:
            conn.close()

    def update_row(self, pk, data: dict) -> None:
        uname = (data.get("username") or data["name"]).strip()
        pwd = data.get("password") or None
        conn = get_connection()
        try:
            cur = conn.cursor()
            row = cur.execute("SELECT user_id FROM staff WHERE staff_id=?", (pk,)).fetchone()
            cur.execute("UPDATE staff SET name=?, phone=? WHERE staff_id=?", (data["name"], data.get("phone", ""), pk))
            try:
                if row and row["user_id"]:
                    cur.execute("UPDATE users SET username=? WHERE user_id=?", (uname, row["user_id"]))
                    if pwd:
                        cur.execute(
                            "UPDATE users SET password_hash=? WHERE user_id=?",
                            (hash_password(pwd), row["user_id"]),
                        )
                else:
                    cur.execute(
                        "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                        (uname, hash_password(pwd or uname), "staff"),
                    )
                    cur.execute("UPDATE staff SET user_id=? WHERE staff_id=?", (cur.lastrowid, pk))
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Username '{uname}' is already taken.") from exc
            conn.commit()
        finally:
            conn.close()

    def delete_row(self, pk) -> None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            row = cur.execute("SELECT user_id FROM staff WHERE staff_id=?", (pk,)).fetchone()
            cur.execute("DELETE FROM staff WHERE staff_id=?", (pk,))
            if row and row["user_id"]:
                cur.execute("DELETE FROM users WHERE user_id=?", (row["user_id"],))
            conn.commit()
        finally:
            conn.close()


# ---- visitors -------------------------------------------------------------------
class VisitorsView(CrudView):
    title = "Visitors"
    headers = ["ID", "Name", "Flat", "Phone", "Vehicle", "Purpose", "In", "Out", "By"]
    select_sql = """
        SELECT v.visitor_id, v.visitor_name, v.flat_no, v.phone, v.vehicle_no,
               v.purpose, v.check_in, COALESCE(v.check_out, '-'), v.recorded_by
        FROM visitors v
    """
    order_by_sql = "ORDER BY v.visitor_id DESC"
    search_cols = ["v.visitor_name", "v.flat_no", "v.phone", "v.vehicle_no"]

    def _apply_role_permissions(self) -> None:
        self.can_edit = False

    def get_form_fields(self) -> list[FieldSpec]:
        return [
            {"name": "visitor_name", "label": "Visitor Name", "required": True},
            {"name": "flat_no", "label": "Flat No", "required": True},
            {"name": "phone", "label": "Phone"},
            {"name": "vehicle_no", "label": "Vehicle No"},
            {"name": "purpose", "label": "Purpose"},
        ]

    def insert_row(self, data: dict) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO visitors (visitor_name, flat_no, phone, vehicle_no, purpose, check_in, recorded_by)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    data["visitor_name"],
                    data["flat_no"],
                    data.get("phone", ""),
                    data.get("vehicle_no", ""),
                    data.get("purpose", ""),
                    now_iso(),
                    self.ctx.get("username", ""),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def custom_actions(self) -> list[tuple[str, str]]:
        return [("checkout", "Check Out")]

    async def handle_extra(self, action_id: str) -> None:
        if action_id != "checkout":
            return
        row = self._selected()
        if row is None:
            self.notify("Select a visitor record.", severity="warning")
            return
        if row[7] != "-":
            self.notify("Visitor has already checked out.", severity="warning")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE visitors SET check_out=? WHERE visitor_id=?", (now_iso(), row[0]))
            conn.commit()
        finally:
            conn.close()
        self.refresh_table()
        self.notify(f"{row[1]} checked out.")


# ---- complaints ------------------------------------------------------------------
class ComplaintsView(CrudView):
    title = "Complaints"
    headers = ["ID", "Resident", "Category", "Status", "Assigned", "Created", "Description"]
    select_sql = """
        SELECT c.complaint_id, COALESCE(r.first_name || ' ' || r.last_name, '-'),
               c.category, c.status, COALESCE(s.name, 'Unassigned'), c.created_at,
               substr(c.description, 1, 50)
        FROM complaints c
        LEFT JOIN residents r ON r.resident_id = c.resident_id
        LEFT JOIN staff s ON s.staff_id = c.assigned_to
    """
    order_by_sql = """
        ORDER BY CASE c.status WHEN 'pending' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
                 c.created_at DESC
    """
    search_cols = ["c.category", "c.status", "c.description", "r.first_name", "r.last_name"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.resident_id is not None:
            self.base_where = "WHERE c.resident_id = ?"
            self.params_fixed = (self.resident_id,)

    def _apply_role_permissions(self) -> None:
        if self.role == "staff":
            self.can_add = self.can_edit = self.can_delete = False
        elif self.role == "resident":
            self.can_edit = self.can_delete = False

    def custom_actions(self) -> list[tuple[str, str]]:
        if self.role == "admin":
            return [("status", "Set Status"), ("assign", "Assign")]
        return []

    def get_form_fields(self) -> list[FieldSpec]:
        fields: list[FieldSpec] = []
        if self.role == "admin" and self.resident_id is None:
            fields.append({"name": "resident_id", "label": "Resident", "type": "select", "required": True, "options": _resident_options()})
        fields.append(
            {
                "name": "category",
                "label": "Category",
                "type": "select",
                "required": True,
                "options": [
                    ("Plumbing", "Plumbing"),
                    ("Electrical", "Electrical"),
                    ("Maintenance", "Maintenance"),
                    ("Cleaning", "Cleaning"),
                    ("Noise", "Noise"),
                    ("Security", "Security"),
                    ("Other", "Other"),
                ],
            }
        )
        fields.append({"name": "description", "label": "Description", "type": "text_area", "required": True})
        return fields

    def get_edit_values(self, pk) -> dict:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT resident_id, category, description FROM complaints WHERE complaint_id=?",
                (pk,),
            ).fetchone()
            if not row:
                return {}
            values = {"category": row["category"], "description": row["description"]}
            if self.role == "admin" and self.resident_id is None:
                values["resident_id"] = str(row["resident_id"]) if row["resident_id"] else ""
            return values
        finally:
            conn.close()

    def insert_row(self, data: dict) -> None:
        resident_id = None
        if self.role == "admin" and self.resident_id is None:
            resident_id = int(data["resident_id"])
        elif self.resident_id is not None:
            resident_id = self.resident_id
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO complaints (resident_id, category, description, status, created_at)
                   VALUES (?,?,?,?,?)""",
                (resident_id, data["category"], data["description"], "pending", now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def update_row(self, pk, data: dict) -> None:
        conn = get_connection()
        try:
            if self.role == "admin" and self.resident_id is None:
                conn.execute(
                    "UPDATE complaints SET resident_id=?, category=?, description=? WHERE complaint_id=?",
                    (int(data["resident_id"]) if data.get("resident_id") else None, data["category"], data["description"], pk),
                )
            else:
                conn.execute(
                    "UPDATE complaints SET category=?, description=? WHERE complaint_id=?",
                    (data["category"], data["description"], pk),
                )
            conn.commit()
        finally:
            conn.close()

    async def handle_extra(self, action_id: str) -> None:
        row = self._selected()
        if row is None:
            self.notify("Select a complaint first.", severity="warning")
            return
        pk = row[0]
        if action_id == "status":
            result = await self.app.push_screen(
                FormModal(
                    "Set Status",
                    [
                        {
                            "name": "status",
                            "label": "Status",
                            "type": "select",
                            "required": True,
"options": [
                            ("Pending", "pending"),
                            ("In Progress", "in_progress"),
                            ("Resolved", "resolved"),
                        ],
                        }
                    ],
                    {"status": row[3]},
                ),
                wait_for_dismiss=True,
            )
            if result is None:
                return
            conn = get_connection()
            try:
                resolved_at = now_iso() if result["status"] == "resolved" else None
                conn.execute(
                    "UPDATE complaints SET status=?, resolved_at=? WHERE complaint_id=?",
                    (result["status"], resolved_at, pk),
                )
                conn.commit()
            finally:
                conn.close()
            self.refresh_table()
            self.notify(f"Complaint #{pk}: {result['status']}.")
        elif action_id == "assign":
            conn = get_connection()
            try:
                current = conn.execute(
                    "SELECT assigned_to FROM complaints WHERE complaint_id=?",
                    (pk,),
                ).fetchone()
            finally:
                conn.close()
            initial = {"staff_id": str(current["assigned_to"]) if current and current["assigned_to"] else "-"}
            result = await self.app.push_screen(
                FormModal(
                    "Assign to Staff",
                    [
                        {
                            "name": "staff_id",
                            "label": "Staff",
                            "type": "select",
                            "required": True,
                            "options": [("Unassigned", "-")] + _staff_options(),
                        }
                    ],
                    initial,
                ),
                wait_for_dismiss=True,
            )
            if result is None:
                return
            assigned = int(result["staff_id"]) if result["staff_id"] != "-" else None
            conn = get_connection()
            try:
                conn.execute("UPDATE complaints SET assigned_to=? WHERE complaint_id=?", (assigned, pk))
                conn.commit()
            finally:
                conn.close()
            self.refresh_table()
            self.notify(f"Complaint #{pk} assignment updated.")


# ---- announcements ---------------------------------------------------------------
class AnnouncementsView(CrudView):
    title = "Announcements"
    headers = ["ID", "Title", "Body", "Posted By", "Date"]
    select_sql = """
        SELECT a.announcement_id, a.title, substr(a.body, 1, 60), a.posted_by, a.created_at
        FROM announcements a
    """
    order_by_sql = "ORDER BY a.created_at DESC"
    search_cols = ["a.title", "a.body", "a.posted_by"]

    def _apply_role_permissions(self) -> None:
        if self.role != "admin":
            self.can_add = self.can_edit = self.can_delete = False

    def get_form_fields(self) -> list[FieldSpec]:
        return [
            {"name": "title", "label": "Title", "required": True},
            {"name": "body", "label": "Body", "type": "text_area", "required": True},
        ]

    def get_edit_values(self, pk) -> dict:
        conn = get_connection()
        try:
            row = conn.execute("SELECT title, body FROM announcements WHERE announcement_id=?", (pk,)).fetchone()
            return {"title": row["title"], "body": row["body"]} if row else {}
        finally:
            conn.close()

    def insert_row(self, data: dict) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO announcements (title, body, posted_by, created_at) VALUES (?,?,?,?)",
                (data["title"], data["body"], self.ctx.get("username", ""), now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def update_row(self, pk, data: dict) -> None:
        conn = get_connection()
        try:
            conn.execute("UPDATE announcements SET title=?, body=? WHERE announcement_id=?", (data["title"], data["body"], pk))
            conn.commit()
        finally:
            conn.close()

    def delete_row(self, pk) -> None:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM announcements WHERE announcement_id=?", (pk,))
            conn.commit()
        finally:
            conn.close()


# ---- maintenance -----------------------------------------------------------------
class MaintenanceView(CrudView):
    title = "Maintenance"
    headers = ["ID", "Resident", "Flat", "Month", "Amount", "Status", "Paid On"]
    select_sql = """
        SELECT m.payment_id, r.first_name || ' ' || r.last_name, r.flat_no,
               m.month, m.amount, CASE WHEN m.paid THEN 'PAID' ELSE 'UNPAID' END,
               COALESCE(m.paid_at, '-')
        FROM maintenance m
        JOIN residents r ON r.resident_id = m.resident_id
    """
    order_by_sql = "ORDER BY m.month DESC, r.flat_no"
    search_cols = ["r.first_name", "r.last_name", "r.flat_no", "m.month"]

    def _apply_role_permissions(self) -> None:
        if self.role != "admin":
            self.can_add = self.can_edit = self.can_delete = False

    def custom_actions(self) -> list[tuple[str, str]]:
        return [("pay", "Mark Paid")] if self.role == "admin" else []

    def get_form_fields(self) -> list[FieldSpec]:
        return [
            {"name": "resident_id", "label": "Resident", "type": "select", "required": True, "options": _resident_options()},
            {"name": "month", "label": "Month (YYYY-MM)", "required": True},
            {"name": "amount", "label": "Amount", "type": "number", "required": True},
        ]

    def get_edit_values(self, pk) -> dict:
        conn = get_connection()
        try:
            row = conn.execute("SELECT resident_id, month, amount FROM maintenance WHERE payment_id=?", (pk,)).fetchone()
            if not row:
                return {}
            return {"resident_id": str(row["resident_id"]), "month": row["month"], "amount": str(row["amount"])}
        finally:
            conn.close()

    def insert_row(self, data: dict) -> None:
        month = data["month"].strip()
        if len(month) != 7 or month[4] != "-":
            raise ValueError("Month must be in YYYY-MM format.")
        conn = get_connection()
        try:
            try:
                conn.execute(
                    "INSERT INTO maintenance (resident_id, month, amount) VALUES (?,?,?)",
                    (int(data["resident_id"]), month, float(data["amount"])),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("A maintenance record for this month already exists.") from exc
            conn.commit()
        finally:
            conn.close()

    def update_row(self, pk, data: dict) -> None:
        month = data["month"].strip()
        if len(month) != 7 or month[4] != "-":
            raise ValueError("Month must be in YYYY-MM format.")
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE maintenance SET resident_id=?, month=?, amount=? WHERE payment_id=?",
                (int(data["resident_id"]), month, float(data["amount"]), pk),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_row(self, pk) -> None:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM maintenance WHERE payment_id=?", (pk,))
            conn.commit()
        finally:
            conn.close()

    async def handle_extra(self, action_id: str) -> None:
        if action_id != "pay":
            return
        row = self._selected()
        if row is None:
            self.notify("Select a maintenance record.", severity="warning")
            return
        if row[5] == "PAID":
            self.notify("Record is already paid.", severity="warning")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE maintenance SET paid=1, paid_at=? WHERE payment_id=?", (now_iso(), row[0]))
            conn.commit()
        finally:
            conn.close()
        self.refresh_table()
        self.notify(f"Payment for {row[1]} ({row[3]}) recorded.")


class MyDuesView(CrudView):
    title = "My Maintenance Dues"
    headers = ["ID", "Month", "Amount", "Status", "Paid On"]
    select_sql = """
        SELECT m.payment_id, m.month, m.amount,
               CASE WHEN m.paid THEN 'PAID' ELSE 'UNPAID' END, COALESCE(m.paid_at, '-')
        FROM maintenance m
    """
    order_by_sql = "ORDER BY m.month DESC"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_where = "WHERE m.resident_id = ?"
        self.params_fixed = (self.resident_id,)

    def _apply_role_permissions(self) -> None:
        self.can_add = self.can_edit = self.can_delete = False


# ---- amenity bookings --------------------------------------------------------------
class AmenityBookingsView(CrudView):
    title = "Amenity Bookings"
    headers = ["ID", "Amenity", "Resident", "Flat", "Date", "Slot", "Status", "Booked"]
    select_sql = """
        SELECT b.booking_id, a.name, r.first_name || ' ' || r.last_name,
               r.flat_no, b.booking_date, b.slot, b.status, b.created_at
        FROM amenity_bookings b
        JOIN amenities a ON a.amenity_id = b.amenity_id
        JOIN residents r ON r.resident_id = b.resident_id
    """
    order_by_sql = "ORDER BY b.booking_date DESC, b.slot"
    search_cols = ["a.name", "b.booking_date", "b.slot", "b.status"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.resident_id is not None:
            self.base_where = "WHERE b.resident_id = ?"
            self.params_fixed = (self.resident_id,)

    def _apply_role_permissions(self) -> None:
        if self.role != "admin":
            self.can_edit = self.can_delete = False

    def custom_actions(self) -> list[tuple[str, str]]:
        if self.role == "admin":
            return [("approve", "Approve"), ("cancel", "Cancel")]
        return []

    def get_form_fields(self) -> list[FieldSpec]:
        fields: list[FieldSpec] = [
            {"name": "amenity_id", "label": "Amenity", "type": "select", "required": True, "options": _amenity_options()},
            {"name": "booking_date", "label": "Date (YYYY-MM-DD)", "required": True},
            {
                "name": "slot",
                "label": "Slot",
                "type": "select",
                "required": True,
                "options": [
                    ("Morning", "Morning"),
                    ("Afternoon", "Afternoon"),
                    ("Evening", "Evening"),
                ],
            },
        ]
        if self.role == "admin" and self.resident_id is None:
            fields.insert(1, {"name": "resident_id", "label": "Resident", "type": "select", "required": True, "options": _resident_options()})
        return fields

    def get_edit_values(self, pk) -> dict:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT amenity_id, resident_id, booking_date, slot FROM amenity_bookings WHERE booking_id=?",
                (pk,),
            ).fetchone()
            if not row:
                return {}
            values = {"amenity_id": str(row["amenity_id"]), "booking_date": row["booking_date"], "slot": row["slot"]}
            if self.role == "admin" and self.resident_id is None:
                values["resident_id"] = str(row["resident_id"])
            return values
        finally:
            conn.close()

    def insert_row(self, data: dict) -> None:
        date = data["booking_date"].strip()
        if len(date) != 10:
            raise ValueError("Date must be in YYYY-MM-DD format.")
        resident_id = int(data["resident_id"]) if self.role == "admin" and self.resident_id is None else self.resident_id
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO amenity_bookings (amenity_id, resident_id, booking_date, slot, status, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (int(data["amenity_id"]), resident_id, date, data["slot"], "pending", now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def update_row(self, pk, data: dict) -> None:
        date = data["booking_date"].strip()
        if len(date) != 10:
            raise ValueError("Date must be in YYYY-MM-DD format.")
        conn = get_connection()
        try:
            if self.role == "admin" and self.resident_id is None:
                conn.execute(
                    "UPDATE amenity_bookings SET amenity_id=?, resident_id=?, booking_date=?, slot=? WHERE booking_id=?",
                    (int(data["amenity_id"]), int(data["resident_id"]), date, data["slot"], pk),
                )
            else:
                conn.execute(
                    "UPDATE amenity_bookings SET amenity_id=?, booking_date=?, slot=? WHERE booking_id=?",
                    (int(data["amenity_id"]), date, data["slot"], pk),
                )
            conn.commit()
        finally:
            conn.close()

    def delete_row(self, pk) -> None:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM amenity_bookings WHERE booking_id=?", (pk,))
            conn.commit()
        finally:
            conn.close()

    async def handle_extra(self, action_id: str) -> None:
        row = self._selected()
        if row is None:
            self.notify("Select a booking first.", severity="warning")
            return
        new_status = {"approve": "confirmed", "cancel": "cancelled"}.get(action_id)
        if new_status is None:
            return
        if row[6] == new_status:
            self.notify(f"Booking is already {new_status}.", severity="warning")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE amenity_bookings SET status=? WHERE booking_id=?", (new_status, row[0]))
            conn.commit()
        finally:
            conn.close()
        self.refresh_table()
        self.notify(f"Booking #{row[0]} is now {new_status}.")


class MyBookingsView(AmenityBookingsView):
    title = "My Amenity Bookings"
    headers = ["ID", "Amenity", "Date", "Slot", "Status", "Booked"]
    select_sql = """
        SELECT b.booking_id, a.name, b.booking_date, b.slot, b.status, b.created_at
        FROM amenity_bookings b
        JOIN amenities a ON a.amenity_id = b.amenity_id
    """
    search_cols = ["a.name", "b.booking_date"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_where = "WHERE b.resident_id = ?"
        self.params_fixed = (self.resident_id,)

    def get_form_fields(self) -> list[FieldSpec]:
        return [
            {"name": "amenity_id", "label": "Amenity", "type": "select", "required": True, "options": _amenity_options()},
            {"name": "booking_date", "label": "Date (YYYY-MM-DD)", "required": True},
            {
                "name": "slot",
                "label": "Slot",
                "type": "select",
                "required": True,
                "options": [
                    ("Morning", "Morning"),
                    ("Afternoon", "Afternoon"),
                    ("Evening", "Evening"),
                ],
            },
        ]

    def get_edit_values(self, pk) -> dict:
        return {}


# ---- parking ----------------------------------------------------------------------
class ParkingView(CrudView):
    title = "Parking"
    headers = ["ID", "Slot", "Vehicle", "Owner", "Flat"]
    select_sql = """
        SELECT p.slot_id, p.slot_no, p.vehicle_no,
               COALESCE(r.first_name || ' ' || r.last_name, '-'),
               COALESCE(r.flat_no, '-')
        FROM parking_slots p
        LEFT JOIN residents r ON r.resident_id = p.resident_id
    """
    order_by_sql = "ORDER BY p.slot_id, p.slot_no"

    def _apply_role_permissions(self) -> None:
        if self.role != "admin":
            self.can_add = self.can_edit = self.can_delete = False

    def get_form_fields(self) -> list[FieldSpec]:
        return [
            {"name": "slot_no", "label": "Slot No", "required": True},
            {"name": "resident_id", "label": "Resident", "type": "select", "required": True, "options": _resident_options()},
            {"name": "vehicle_no", "label": "Vehicle No"},
        ]

    def get_edit_values(self, pk) -> dict:
        conn = get_connection()
        try:
            row = conn.execute("SELECT slot_no, resident_id, vehicle_no FROM parking_slots WHERE slot_id=?", (pk,)).fetchone()
            if not row:
                return {}
            return {
                "slot_no": row["slot_no"],
                "resident_id": str(row["resident_id"]) if row["resident_id"] else "",
                "vehicle_no": row["vehicle_no"],
            }
        finally:
            conn.close()

    def insert_row(self, data: dict) -> None:
        conn = get_connection()
        try:
            try:
                conn.execute(
                    "INSERT INTO parking_slots (slot_no, resident_id, vehicle_no) VALUES (?,?,?)",
                    (data["slot_no"].strip(), int(data["resident_id"]), data.get("vehicle_no", "")),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Slot '{data['slot_no'].strip()}' already exists.") from exc
            conn.commit()
        finally:
            conn.close()

    def update_row(self, pk, data: dict) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE parking_slots SET slot_no=?, resident_id=?, vehicle_no=? WHERE slot_id=?",
                (data["slot_no"].strip(), int(data["resident_id"]) if data.get("resident_id") else None, data.get("vehicle_no", ""), pk),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_row(self, pk) -> None:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM parking_slots WHERE slot_id=?", (pk,))
            conn.commit()
        finally:
            conn.close()


# ---- resident profile ---------------------------------------------------------------
class ProfileView(Vertical):
    def __init__(self, ctx: dict, **kwargs):
        super().__init__(**kwargs)
        self.ctx = ctx

    def compose(self) -> ComposeResult:
        yield Static("My Profile", id="crud-title", classes="crud-title")
        yield Static("", id="profile-details", classes="profile-details")
        with Vertical(classes="profile-form"):
            yield Label("New Password")
            yield Input(id="pwd-new", password=True)
            yield Label("Confirm Password")
            yield Input(id="pwd-confirm", password=True)
            yield Button("Change Password", id="profile-change", variant="primary")

    def on_mount(self) -> None:
        self.refresh_profile()

    def refresh_profile(self) -> None:
        box = self.query_one("#profile-details", Static)
        box.update(
            f"Name: {self.ctx.get('display_name','')}\n"
            f"Username: {self.ctx.get('username','')}\n"
            f"Flat: {self.ctx.get('flat_no','-')}"
        )

    @on(Button.Pressed, "#profile-change")
    def _change_password(self) -> None:
        new = self.query_one("#pwd-new", Input).value
        confirm = self.query_one("#pwd-confirm", Input).value
        if not new:
            self.notify("Enter a new password.", severity="warning")
            return
        if new != confirm:
            self.notify("Passwords do not match.", severity="error")
            return
        change_password(self.ctx["user_id"], new)
        self.query_one("#pwd-new", Input).value = ""
        self.query_one("#pwd-confirm", Input).value = ""
        self.notify("Password updated.")