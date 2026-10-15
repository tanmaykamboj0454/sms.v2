import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="sms_v2_demo_test_")
os.environ["SMS_V2_DB"] = str(Path(_TMP) / "test.db")

import pytest  # noqa: E402

from db.database import authenticate, get_connection, initialise_database, seed_demo_data  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    from db.database import DB_PATH

    if DB_PATH.exists():
        DB_PATH.unlink()
    initialise_database()
    yield


def _counts():
    conn = get_connection()
    try:
        tables = [
            "residents", "staff", "visitors", "complaints",
            "announcements", "maintenance", "amenity_bookings", "parking_slots",
        ]
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    finally:
        conn.close()


def test_seed_demo_data_populates_and_is_idempotent():
    seed_demo_data()
    counts = _counts()
    assert counts["residents"] == 5
    assert counts["staff"] == 2
    assert counts["visitors"] == 3
    assert counts["complaints"] == 4
    assert counts["announcements"] == 3
    assert counts["maintenance"] == 8
    assert counts["amenity_bookings"] == 4
    assert counts["parking_slots"] == 3

    seed_demo_data()
    assert _counts() == counts


def test_seed_status_mix():
    seed_demo_data()
    conn = get_connection()
    try:
        statuses = [r[0] for r in conn.execute("SELECT DISTINCT status FROM complaints")]
        assert len(statuses) == 3
        payments = [r[0] for r in conn.execute("SELECT DISTINCT paid FROM maintenance")]
        assert set(payments) == {0, 1}
    finally:
        conn.close()


def test_demo_users_can_log_in():
    seed_demo_data()
    assert authenticate("aman101", "101") is not None
    assert authenticate("rajesh", "demo123") is not None
    assert authenticate("aman101", "wrong") is None