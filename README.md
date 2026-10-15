# sms.v2

Society Management System V2 — a terminal User Interface (TUI) built with
[Textual](https://textual.textize.io) and SQLite.

## Features

- Role-based login: **Admin**, **Security/Staff**, and **Resident**
- Residents: add, edit, search, delete, with auto-provisioned login accounts
- Visitor in/out log with one-click check-out (security)
- Security staff account management
- Complaints: submit, assign to staff, track `pending → in_progress → resolved`
- Announcements: admin posts notices; staff and residents view them
- Maintenance: monthly dues per resident, mark paid, resident view of own dues
- Amenity booking: clubhouse/gym/pool/hall bookings with approve/cancel workflow
- Parking: allocate slots to residents/vehicles

## Tech stack

- Python 3.11+
- [Textual](https://textual.textize.io) TUI framework
- SQLite (stdlib `sqlite3`) — zero-config, single `sms_v2.db` file
- Passwords hashed with PBKDF2-SHA256 (no plaintext storage)

## Install & run

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

The schema and seed data (admin account, amenity list) are created on first run.
The database lives at `sms_v2.db` in the project root. Override the location
with the `SMS_V2_DB` environment variable.

Default login: **admin / admin123**

## Demo data

Populate the database with sample residents, staff, visitors, complaints,
announcements, bills, bookings and parking slots before starting:

```bash
python main.py --demo
```

Demo logins:
- Residents: `aman101` / `101`, `neha102` / `102`, `rohan201` / `201`, `priya301` / `301`, `suresh302` / `302` (password = flat no)
- Security staff: `rajesh` / `demo123`, `meena` / `demo123`

Seeding is idempotent — it only runs when no residents exist yet.

## Roles

| Module             | Admin              | Staff            | Resident            |
|--------------------|--------------------|------------------|---------------------|
| Residents          | full CRUD          | view             | own profile         |
| Visitors           | full CRUD + out    | add + checkout   | —                   |
| Security accounts  | full CRUD          | —                | —                   |
| Complaints         | assign/resolve     | view             | submit + track own  |
| Announcements      | post               | view             | view                |
| Maintenance        | bill/mark paid     | —                | view own dues       |
| Amenity bookings   | manage/approve     | —                | book own            |
| Parking            | allocate/manage    | view             | —                   |

## Controls

- `Tab` / arrows: navigate
- `Enter`: activate (submit forms, run actions)
- `Ctrl+L`: logout (on dashboards)
- `Ctrl+Q`: quit

## Project layout

```
main.py            entry point
app.py             Textual app shell + theme CSS
db/                schema.sql + SQLite helpers (hashing, auth, session)
ui/
  widgets.py       reusable DataTable CRUD view, form/confirm modals
  modules.py       8 module views + resident profile
  login.py         login screen
  dashboards.py    role-based tabbed dashboards
tests/             pytest smoke + module tests (headless Textual pilot)
```

## Tests

```bash
python -m pytest tests -q
```

Tests run against a temporary SQLite database and drive the TUI headless with
Textual's `run_test` pilot.