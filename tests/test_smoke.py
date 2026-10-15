import asyncio
import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="sms_v2_test_")
os.environ["SMS_V2_DB"] = str(Path(_TMP) / "test.db")

from db.database import (  # noqa: E402
    authenticate,
    build_session,
    get_connection,
    hash_password,
    initialise_database,
    verify_password,
)


def test_db_initialises_all_tables():
    initialise_database()
    conn = get_connection()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for table in (
        "users",
        "residents",
        "staff",
        "visitors",
        "complaints",
        "announcements",
        "maintenance",
        "amenities",
        "amenity_bookings",
        "parking_slots",
    ):
        assert table in tables


def test_password_hashing_roundtrip():
    stored = hash_password("secret123")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("secret123", stored)
    assert not verify_password("nope", stored)


def test_admin_seed_login():
    initialise_database()
    user = authenticate("admin", "admin123")
    assert user is not None
    assert user["role"] == "admin"
    assert authenticate("admin", "wrong") is None
    assert authenticate("ghost", "x") is None


def test_resident_creation_and_login():
    from ui.modules import ResidentsView

    initialise_database()
    view = ResidentsView(ctx={}, role="admin")
    view.insert_row(
        {
            "first_name": "Asha",
            "last_name": "Sharma",
            "flat_no": "101",
            "phone": "9876543210",
            "email": "",
            "username": "asha101",
            "password": "pw101",
        }
    )
    user = authenticate("asha101", "pw101")
    assert user is not None
    assert user["role"] == "resident"
    session = build_session(user)
    assert session["resident_id"] is not None
    assert session["flat_no"] == "101"
    assert session["display_name"] == "Asha Sharma"


def test_security_staff_creation_and_login():
    from ui.modules import SecurityView

    initialise_database()
    view = SecurityView(ctx={}, role="admin")
    view.insert_row({"name": "Rajesh Guard", "phone": "111", "username": "rajesh", "password": "rpw"})
    user = authenticate("rajesh", "rpw")
    assert user is not None
    assert user["role"] == "staff"
    session = build_session(user)
    assert session["staff_id"] is not None
    assert session["display_name"] == "Rajesh Guard"


def test_app_headless_login_admin_dashboard():
    from app import SMSApp
    from textual.widgets import Input, Tab, TabbedContent

    async def scenario():
        from ui.login import LoginScreen
        from ui.dashboards import DashboardScreen

        app = SMSApp()
        async with app.run_test(size=(120, 32)) as pilot:
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
            assert isinstance(app.screen, DashboardScreen)
            tabbed = app.screen.query_one(TabbedContent)
            labels = [tab.label.plain for tab in tabbed.query(Tab)]
            assert "Residents" in labels
            assert "Maintenance" in labels
            assert "Parking" in labels

    asyncio.run(scenario())