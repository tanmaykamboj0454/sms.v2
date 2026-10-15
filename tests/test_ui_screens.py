"""Headless UI sweep: mounts every dashboard tab and exercises every modal/
action flow so that compose-time and handler-time errors (like the ConfirmModal
margin kwarg bug) surface in CI."""
import asyncio
import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="sms_v2_ui_screen_test_")
os.environ["SMS_V2_DB"] = str(Path(_TMP) / "test.db")

from db.database import get_connection, hash_password, initialise_database  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    from db.database import DB_PATH

    if DB_PATH.exists():
        DB_PATH.unlink()
    initialise_database()
    yield


def _seed():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", ("asha", hash_password("pw"), "resident"))
        asha_uid = cur.lastrowid
        cur.execute("INSERT INTO residents (first_name,last_name,flat_no,phone,email,user_id) VALUES (?,?,?,?,?,?)", ("Asha", "Sharma", "101", "", "", asha_uid))
        cur.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", ("rajesh", hash_password("pw"), "staff"))
        rajesh_uid = cur.lastrowid
        cur.execute("INSERT INTO staff (name,phone,user_id) VALUES (?,?,?)", ("Rajesh", "", rajesh_uid))
        cur.execute("INSERT INTO visitors (visitor_name,flat_no,phone,vehicle_no,purpose,check_in) VALUES (?,?,?,?,?,?)", ("Vikram", "101", "1", "DL-01", "Delivery", "2026-09-28 09:00:00"))
        cur.execute(
            "INSERT INTO complaints (resident_id,category,description,status,created_at) VALUES (?,?,?,?,?)",
            (1, "Plumbing", "Leak in bathroom", "pending", "2026-09-28 10:00:00"),
        )
        cur.execute(
            "INSERT INTO maintenance (resident_id,month,amount,paid,paid_at) VALUES (?,?,?,?,?)",
            (1, "2026-09", 1500, 0, None),
        )
        cur.execute(
            "INSERT INTO amenity_bookings (amenity_id,resident_id,booking_date,slot,status,created_at) VALUES (?,?,?,?,?,?)",
            (1, 1, "2026-10-04", "Evening", "pending", "2026-09-28 11:00:00"),
        )
        cur.execute("INSERT INTO parking_slots (slot_no,resident_id,vehicle_no) VALUES (?,?,?)", ("P-01", 1, "DL-01-AB"))
        cur.execute("INSERT INTO announcements (title,body,posted_by,created_at) VALUES (?,?,?,?)", ("Water shutdown", "No water on Sunday", "admin", "2026-09-28 08:00:00"))
        conn.commit()
    finally:
        conn.close()


async def _login(pilot, app, user, pwd):
    from ui.login import LoginScreen
    from ui.dashboards import DashboardScreen
    from textual.widgets import Input

    for _ in range(50):
        await pilot.pause()
        if isinstance(app.screen, LoginScreen):
            break
    app.screen.query_one("#login-user", Input).value = user
    app.screen.query_one("#login-pass", Input).value = pwd
    await pilot.press("enter")
    await _wait_screen(pilot, app, DashboardScreen)


async def _wait_screen(pilot, app, kind):
    for _ in range(80):
        await pilot.pause()
        if isinstance(app.screen, kind):
            return
    raise AssertionError(f"expected screen {kind.__name__}, got {type(app.screen).__name__}")


async def _goto_tab(pilot, app, label):
    from textual.widgets import Tab, TabbedContent

    tabbed = app.screen.query_one(TabbedContent)
    tab = next(t for t in tabbed.query(Tab) if t.label.plain == label)
    await pilot.click(tab)
    for _ in range(10):
        await pilot.pause()


async def _press(pilot, widget):
    widget.focus()
    await pilot.pause()
    await pilot.press("enter")


def _view(app, cls):
    return app.screen.query(cls).first()


def _first_row(view):
    from textual.widgets import DataTable

    table = view.query_one(f"#{view._tid('table')}", DataTable)
    if table.row_count:
        table.move_cursor(row=0)
    return table


def _tabs(app):
    from textual.widgets import Tab, TabbedContent

    return [t.label.plain for t in app.screen.query_one(TabbedContent).query(Tab)]


def test_admin_dashboard_tabs_and_add_modals():
    from app import SMSApp
    from ui.dashboards import DashboardScreen
    from ui.modules import (
        AmenityBookingsView,
        AnnouncementsView,
        ComplaintsView,
        MaintenanceView,
        ParkingView,
        ResidentsView,
        SecurityView,
        VisitorsView,
    )
    from ui.widgets import FormModal

    _seed()

    async def scenario():
        app = SMSApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await _login(pilot, app, "admin", "admin123")
            expected = ["Residents", "Visitors", "Security", "Complaints", "Announcements", "Maintenance", "Amenities", "Parking"]
            assert _tabs(app) == expected

            view_types = [ResidentsView, VisitorsView, SecurityView, ComplaintsView, AnnouncementsView, MaintenanceView, AmenityBookingsView, ParkingView]
            for label, cls in zip(expected, view_types):
                await _goto_tab(pilot, app, label)
                view = _view(app, cls)
                _first_row(view)
                await pilot.pause()
                add = view.query_one(f"#{view._tid('btn-add')}", __import__("textual.widgets", fromlist=["Button"]).Button)
                await _press(pilot, add)
                await _wait_screen(pilot, app, FormModal)
                cancel = app.screen.query_one("#form-cancel", __import__("textual.widgets", fromlist=["Button"]).Button)
                await _press(pilot, cancel)
                await _wait_screen(pilot, app, DashboardScreen)
                assert app._exception is None

    asyncio.run(scenario())


def test_admin_delete_confirm_flow():
    from app import SMSApp
    from ui.dashboards import DashboardScreen
    from ui.modules import ResidentsView
    from ui.widgets import ConfirmModal
    from textual.widgets import Button

    _seed()

    async def scenario():
        app = SMSApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await _login(pilot, app, "admin", "admin123")
            view = _view(app, ResidentsView)
            _first_row(view)
            delete_btn = view.query_one(f"#{view._tid('btn-delete')}", Button)
            await _press(pilot, delete_btn)
            await _wait_screen(pilot, app, ConfirmModal)
            no = app.screen.query_one("#confirm-no", Button)
            await _press(pilot, no)
            await _wait_screen(pilot, app, DashboardScreen)
            assert len(_view(app, ResidentsView).get_rows()) == 1
            _first_row(view)
            await _press(pilot, delete_btn)
            await _wait_screen(pilot, app, ConfirmModal)
            yes = app.screen.query_one("#confirm-yes", Button)
            await _press(pilot, yes)
            await _wait_screen(pilot, app, DashboardScreen)
            assert len(_view(app, ResidentsView).get_rows()) == 0

    asyncio.run(scenario())


def test_admin_custom_actions():
    from app import SMSApp
    from ui.dashboards import DashboardScreen
    from ui.modules import AmenityBookingsView, ComplaintsView, VisitorsView
    from ui.widgets import FormModal
    from textual.widgets import Button

    _seed()

    async def scenario():
        app = SMSApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await _login(pilot, app, "admin", "admin123")

            await _goto_tab(pilot, app, "Visitors")
            view = _view(app, VisitorsView)
            table = _first_row(view)
            assert view.get_rows()[0][7] == "-"
            await _press(pilot, view.query_one(f"#{view._tid('act-checkout')}", Button))
            await pilot.pause()
            assert view.get_rows()[0][7] != "-"

            await _goto_tab(pilot, app, "Complaints")
            view = _view(app, ComplaintsView)
            _first_row(view)
            await _press(pilot, view.query_one(f"#{view._tid('act-status')}", Button))
            await _wait_screen(pilot, app, FormModal)
            assert app.screen.query_one("#field-status")
            await _press(pilot, app.screen.query_one("#form-cancel", Button))
            await _wait_screen(pilot, app, DashboardScreen)

            _first_row(view)
            await _press(pilot, view.query_one(f"#{view._tid('act-assign')}", Button))
            await _wait_screen(pilot, app, FormModal)
            assert app.screen.query_one("#field-staff_id")
            await _press(pilot, app.screen.query_one("#form-cancel", Button))
            await _wait_screen(pilot, app, DashboardScreen)

            await _goto_tab(pilot, app, "Amenities")
            view = _view(app, AmenityBookingsView)
            _first_row(view)
            await _press(pilot, view.query_one(f"#{view._tid('act-approve')}", Button))
            await pilot.pause()
            assert view.get_rows()[0][6] == "confirmed"
            assert app._exception is None

    asyncio.run(scenario())


def test_admin_edit_modal_opens_with_prefill():
    from app import SMSApp
    from ui.dashboards import DashboardScreen
    from ui.modules import ResidentsView
    from ui.widgets import FormModal
    from textual.widgets import Button, Input

    _seed()

    async def scenario():
        app = SMSApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await _login(pilot, app, "admin", "admin123")
            view = _view(app, ResidentsView)
            _first_row(view)
            await _press(pilot, view.query_one(f"#{view._tid('btn-edit')}", Button))
            await _wait_screen(pilot, app, FormModal)
            modal = app.screen
            assert modal.query_one("#field-first_name", Input).value == "Asha"
            modal.query_one("#field-first_name", Input).value = "Asha2"
            await _press(pilot, modal.query_one("#form-save", Button))
            await _wait_screen(pilot, app, DashboardScreen)
            assert _view(app, ResidentsView).get_rows()[0][1] == "Asha2"

    asyncio.run(scenario())


def test_staff_dashboard_and_flows():
    from app import SMSApp
    from ui.dashboards import DashboardScreen
    from ui.modules import ResidentsView, VisitorsView
    from ui.widgets import FormModal
    from textual.widgets import Button

    _seed()

    async def scenario():
        app = SMSApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await _login(pilot, app, "rajesh", "pw")
            assert _tabs(app) == ["Visitors", "Residents", "Complaints", "Announcements", "Parking"]

            await _goto_tab(pilot, app, "Residents")
            view = _view(app, ResidentsView)
            assert len(view.query(f"#{view._tid('btn-add')}")) == 0

            await _goto_tab(pilot, app, "Visitors")
            view = _view(app, VisitorsView)
            table = _first_row(view)
            assert table.row_count == 1
            await _press(pilot, view.query_one(f"#{view._tid('act-checkout')}", Button))
            await pilot.pause()
            assert view.get_rows()[0][7] != "-"

            add = view.query_one(f"#{view._tid('btn-add')}", Button)
            await _press(pilot, add)
            await _wait_screen(pilot, app, FormModal)
            await _press(pilot, app.screen.query_one("#form-cancel", Button))
            await _wait_screen(pilot, app, DashboardScreen)
            assert app._exception is None

    asyncio.run(scenario())


def test_resident_dashboard_and_modals():
    from app import SMSApp
    from ui.dashboards import DashboardScreen
    from ui.modules import ComplaintsView, MyBookingsView
    from ui.widgets import FormModal
    from textual.widgets import Button

    _seed()

    async def scenario():
        app = SMSApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await _login(pilot, app, "asha", "pw")
            assert _tabs(app) == ["Announcements", "My Complaints", "My Bookings", "My Dues", "Profile"]

            for label in _tabs(app):
                await _goto_tab(pilot, app, label)
                await pilot.pause()
                assert app._exception is None

            await _goto_tab(pilot, app, "My Complaints")
            await _goto_tab(pilot, app, "My Complaints")
            view = _view(app, ComplaintsView)
            add = view.query_one(f"#{view._tid('btn-add')}", Button)
            await _press(pilot, add)
            await _wait_screen(pilot, app, FormModal)
            assert app.screen.query_one("#field-description")
            await _press(pilot, app.screen.query_one("#form-cancel", Button))
            await _wait_screen(pilot, app, DashboardScreen)

            await _goto_tab(pilot, app, "My Bookings")
            assert len(_view(app, MyBookingsView).get_rows()) == 1

    asyncio.run(scenario())