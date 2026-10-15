import asyncio
import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="sms_v2_module_test_")
os.environ["SMS_V2_DB"] = str(Path(_TMP) / "test.db")

from db.database import (  # noqa: E402
    authenticate,
    build_session,
    get_connection,
    initialise_database,
)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    from db.database import DB_PATH

    if DB_PATH.exists():
        DB_PATH.unlink()
    initialise_database()
    yield


def _admin():
    return {"role": "admin", "username": "admin"}


def _make_resident(first="Asha", last="Sharma", flat="101", username="asha"):
    from ui.modules import ResidentsView

    ResidentsView(ctx=_admin(), role="admin").insert_row(
        {"first_name": first, "last_name": last, "flat_no": flat, "phone": "", "email": "", "username": username, "password": "pw"}
    )


def _make_staff(name="Rajesh", username="rajesh"):
    from ui.modules import SecurityView

    SecurityView(ctx=_admin(), role="admin").insert_row({"name": name, "phone": "", "username": username, "password": "pw"})


def _resident_session(username="asha"):
    return build_session(authenticate(username, "pw"))


def test_resident_view_crud_and_permissions():
    from ui.modules import ResidentsView

    initialise_database()
    _make_resident()
    view = ResidentsView(ctx=_admin(), role="admin")
    assert view.get_rows() and view.get_rows()[0][0] == 1
    view.update_row(1, {"first_name": "Asha", "last_name": "Khan", "flat_no": "102", "phone": "9", "email": "", "username": "asha", "password": ""})
    conn = get_connection()
    row = conn.execute("SELECT flat_no, last_name FROM residents WHERE resident_id=1").fetchone()
    conn.close()
    assert row["flat_no"] == "102" and row["last_name"] == "Khan"
    view.delete_row(1)
    assert not view.get_rows()

    viewer = ResidentsView(ctx=_admin(), role="staff")
    assert not viewer.can("add") and not viewer.can("edit") and not viewer.can("delete")


def test_visitors_checkout_flow():
    from ui.modules import VisitorsView

    initialise_database()
    view = VisitorsView(ctx={"username": "rajesh"}, role="staff")
    view.insert_row({"visitor_name": "Vikram", "flat_no": "101", "phone": "1", "vehicle_no": "DL-01", "purpose": "Delivery"})
    rows = view.get_rows()
    assert rows[0][1] == "Vikram" and rows[0][7] == "-"
    conn = get_connection()
    conn.execute("UPDATE visitors SET check_out=? WHERE visitor_id=?", ("2026-01-01 10:00:00", rows[0][0]))
    conn.commit()
    conn.close()
    assert view.get_rows()[0][7] != "-"


def test_complaints_admin_and_resident_flow():
    from ui.modules import ComplaintsView

    initialise_database()
    _make_resident()
    _make_staff()
    admin_view = ComplaintsView(ctx=_admin(), role="admin")
    admin_view.insert_row({"resident_id": "1", "category": "Plumbing", "description": "Leak in bathroom"})
    conn = get_connection()
    conn.execute("UPDATE complaints SET status='in_progress', assigned_to=1 WHERE complaint_id=1")
    conn.commit()
    conn.close()
    rows = admin_view.get_rows()
    assert rows[0][3] == "in_progress" and rows[0][4] == "Rajesh"

    resident = _resident_session()
    own = ComplaintsView(ctx=resident, role="resident", resident_id=resident["resident_id"])
    own.insert_row({"category": "Noise", "description": "Loud music"})
    own_rows = own.get_rows()
    assert len(own_rows) == 2
    assert not own.can("edit") and not own.can("delete") and own.can("add")


def test_maintenance_and_dues():
    from ui.modules import MaintenanceView, MyDuesView

    initialise_database()
    _make_resident()
    view = MaintenanceView(ctx=_admin(), role="admin")
    view.insert_row({"resident_id": "1", "month": "2026-06", "amount": "1500"})
    conn = get_connection()
    conn.execute("UPDATE maintenance SET paid=1, paid_at=? WHERE payment_id=1", ("2026-06-15",))
    conn.commit()
    conn.close()
    rows = view.get_rows()
    assert rows[0][5] == "PAID"
    resident = _resident_session()
    dues = MyDuesView(ctx=resident, role="resident", resident_id=resident["resident_id"])
    assert len(dues.get_rows()) == 1


def test_amenity_bookings():
    from ui.modules import AmenityBookingsView, MyBookingsView

    initialise_database()
    _make_resident()
    admin = AmenityBookingsView(ctx=_admin(), role="admin")
    admin.insert_row({"amenity_id": "1", "resident_id": "1", "booking_date": "2026-07-04", "slot": "Evening"})
    conn = get_connection()
    conn.execute("UPDATE amenity_bookings SET status='confirmed' WHERE booking_id=1")
    conn.commit()
    conn.close()
    assert admin.get_rows()[0][6] == "confirmed"
    resident = _resident_session()
    own = MyBookingsView(ctx=resident, role="resident", resident_id=resident["resident_id"])
    assert len(own.get_rows()) == 1


def test_parking_allocation():
    from ui.modules import ParkingView

    initialise_database()
    _make_resident()
    view = ParkingView(ctx=_admin(), role="admin")
    view.insert_row({"slot_no": "P-01", "resident_id": "1", "vehicle_no": "DL-01-AB"})
    rows = view.get_rows()
    assert rows[0][1] == "P-01" and rows[0][4] == "101"
    staff_view = ParkingView(ctx=_admin(), role="staff")
    assert not staff_view.can("add")


def test_announcements_posted_by_admin():
    from ui.modules import AnnouncementsView

    initialise_database()
    view = AnnouncementsView(ctx=_admin(), role="admin")
    view.insert_row({"title": "Water shutdown", "body": "No water on Sunday"})
    rows = view.get_rows()
    assert rows[0][1] == "Water shutdown" and rows[0][3] == "admin"


def test_ui_add_resident_modal_flow():
    from app import SMSApp
    from ui.login import LoginScreen
    from ui.dashboards import DashboardScreen
    from ui.modules import ResidentsView
    from ui.widgets import FormModal
    from textual.widgets import Button, Input

    initialise_database()

    async def scenario():
        app = SMSApp()
        async with app.run_test(size=(120, 50)) as pilot:
            for _ in range(50):
                await pilot.pause()
                if isinstance(app.screen, LoginScreen):
                    break
            app.screen.query_one("#login-user", Input).value = "admin"
            app.screen.query_one("#login-pass", Input).value = "admin123"
            await pilot.press("enter")
            for _ in range(50):
                await pilot.pause()
                if isinstance(app.screen, DashboardScreen):
                    break
            view = app.screen.query(ResidentsView).first()
            await pilot.click(view.query_one(f"#{view._tid('btn-add')}", Button))
            for _ in range(50):
                await pilot.pause()
                if isinstance(app.screen, FormModal):
                    break
            modal = app.screen
            modal.query_one("#field-first_name", Input).value = "Ravi"
            modal.query_one("#field-last_name", Input).value = "Kumar"
            modal.query_one("#field-flat_no", Input).value = "203"
            modal.query_one("#field-username", Input).value = "ravi203"
            save = modal.query_one("#form-save", Button)
            save.focus()
            await pilot.pause()
            await pilot.press("enter")
            for _ in range(50):
                await pilot.pause()
                if isinstance(app.screen, DashboardScreen):
                    break
            conn = get_connection()
            count = conn.execute("SELECT COUNT(*) FROM residents").fetchone()[0]
            conn.close()
            assert count == 1
            assert authenticate("ravi203", "203") is not None

    asyncio.run(scenario())


def test_ui_resident_dashboard_tabs():
    from app import SMSApp
    from ui.login import LoginScreen
    from ui.dashboards import DashboardScreen
    from textual.widgets import Input, Tab, TabbedContent

    initialise_database()
    _make_resident(username="mom")

    async def scenario():
        app = SMSApp()
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(50):
                await pilot.pause()
                if isinstance(app.screen, LoginScreen):
                    break
            app.screen.query_one("#login-user", Input).value = "mom"
            app.screen.query_one("#login-pass", Input).value = "pw"
            await pilot.press("enter")
            for _ in range(50):
                await pilot.pause()
                if isinstance(app.screen, DashboardScreen):
                    break
            tabbed = app.screen.query_one(TabbedContent)
            labels = [tab.label.plain for tab in tabbed.query(Tab)]
            assert "My Complaints" in labels
            assert "My Bookings" in labels
            assert "My Dues" in labels
            assert "Profile" in labels
            assert "Maintenance" not in labels

    asyncio.run(scenario())