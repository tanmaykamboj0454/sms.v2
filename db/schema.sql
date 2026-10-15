PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'resident' CHECK (role IN ('admin','staff','resident')),
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS residents (
    resident_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    flat_no TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS visitors (
    visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    visitor_name TEXT NOT NULL,
    flat_no TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    vehicle_no TEXT NOT NULL DEFAULT '',
    purpose TEXT NOT NULL DEFAULT '',
    check_in TEXT NOT NULL,
    check_out TEXT,
    recorded_by TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER,
    category TEXT NOT NULL DEFAULT 'Other',
    description TEXT NOT NULL,
    assigned_to INTEGER,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','resolved')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (resident_id) REFERENCES residents(resident_id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_to) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS announcements (
    announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    posted_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    resident_id INTEGER NOT NULL,
    month TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    paid INTEGER NOT NULL DEFAULT 0,
    paid_at TEXT,
    UNIQUE (resident_id, month),
    FOREIGN KEY (resident_id) REFERENCES residents(resident_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS amenities (
    amenity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS amenity_bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    amenity_id INTEGER NOT NULL,
    resident_id INTEGER NOT NULL,
    booking_date TEXT NOT NULL,
    slot TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed','cancelled')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (amenity_id) REFERENCES amenities(amenity_id) ON DELETE CASCADE,
    FOREIGN KEY (resident_id) REFERENCES residents(resident_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS parking_slots (
    slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_no TEXT NOT NULL UNIQUE,
    resident_id INTEGER,
    vehicle_no TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (resident_id) REFERENCES residents(resident_id) ON DELETE SET NULL
);