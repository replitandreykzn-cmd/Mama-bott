import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "mama_bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_premium INTEGER DEFAULT 0,
            premium_until TEXT,
            trial_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS family_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL,
            member_user_id INTEGER NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_user_id, member_user_id),
            FOREIGN KEY (owner_user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS children (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            birthdate TEXT NOT NULL,
            gender TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS growth_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            height_cm REAL,
            weight_kg REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (child_id) REFERENCES children(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vaccinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            vaccine_name TEXT NOT NULL,
            scheduled_date TEXT,
            done_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (child_id) REFERENCES children(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            child_id INTEGER,
            title TEXT NOT NULL,
            remind_at TEXT NOT NULL,
            repeat_type TEXT DEFAULT 'none',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS photo_diary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            caption TEXT,
            photo_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (child_id) REFERENCES children(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dose TEXT,
            interval_hours REAL NOT NULL,
            next_reminder_at TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (child_id) REFERENCES children(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS illness_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            illness_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (child_id) REFERENCES children(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS illness_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            illness_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            temperature REAL,
            symptoms TEXT,
            medications_given TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Миграции для существующих БД
    for migration in [
        "ALTER TABLE users ADD COLUMN trial_used INTEGER DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS family_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL,
            member_user_id INTEGER NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_user_id, member_user_id),
            FOREIGN KEY (owner_user_id) REFERENCES users(user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS photo_diary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            caption TEXT,
            photo_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dose TEXT,
            interval_hours REAL NOT NULL,
            next_reminder_at TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS illness_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            illness_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS illness_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            illness_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            temperature REAL,
            symptoms TEXT,
            medications_given TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
    ]:
        try:
            c.execute(migration)
        except Exception:
            pass

    conn.commit()
    conn.close()


def upsert_user(user_id, username, first_name):
    """Возвращает True если пользователь новый."""
    conn = get_conn()
    c = conn.cursor()
    existing = c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    is_new = existing is None
    c.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()
    return is_new


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def activate_trial(user_id):
    """Активирует 14-дневный пробный период. Возвращает дату окончания или None если уже использован."""
    user = get_user(user_id)
    if user and user["trial_used"]:
        return None
    until = (datetime.now() + timedelta(days=14)).isoformat()
    conn = get_conn()
    conn.execute(
        "UPDATE users SET is_premium=1, premium_until=?, trial_used=1 WHERE user_id=?",
        (until, user_id)
    )
    conn.commit()
    conn.close()
    return until


def set_premium(user_id, until_date: str):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?",
        (until_date, user_id)
    )
    conn.commit()
    conn.close()


def is_premium(user_id):
    """Проверяет Premium у пользователя или у владельца семьи, в которую он добавлен."""
    if _check_premium_direct(user_id):
        return True
    conn = get_conn()
    owners = conn.execute(
        "SELECT owner_user_id FROM family_members WHERE member_user_id=?", (user_id,)
    ).fetchall()
    conn.close()
    for row in owners:
        if _check_premium_direct(row["owner_user_id"]):
            return True
    return False


def _check_premium_direct(user_id):
    user = get_user(user_id)
    if not user or not user["is_premium"]:
        return False
    if user["premium_until"]:
        until = datetime.fromisoformat(user["premium_until"])
        if until < datetime.now():
            conn = get_conn()
            conn.execute("UPDATE users SET is_premium=0 WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
            return False
    return True


# ── Семейный доступ ──────────────────────────────────────────────────────────

def add_family_member(owner_user_id, member_user_id):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO family_members (owner_user_id, member_user_id) VALUES (?,?)",
            (owner_user_id, member_user_id)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def remove_family_member(owner_user_id, member_user_id):
    conn = get_conn()
    conn.execute(
        "DELETE FROM family_members WHERE owner_user_id=? AND member_user_id=?",
        (owner_user_id, member_user_id)
    )
    conn.commit()
    conn.close()


def get_family_members(owner_user_id):
    conn = get_conn()
    rows = conn.execute(
        """SELECT fm.member_user_id, u.username, u.first_name
           FROM family_members fm
           LEFT JOIN users u ON u.user_id = fm.member_user_id
           WHERE fm.owner_user_id=?""",
        (owner_user_id,)
    ).fetchall()
    conn.close()
    return rows


def get_family_owner(member_user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT owner_user_id FROM family_members WHERE member_user_id=?", (member_user_id,)
    ).fetchone()
    conn.close()
    return row["owner_user_id"] if row else None


# ── Дети ─────────────────────────────────────────────────────────────────────

def get_children(user_id):
    owner = get_family_owner(user_id)
    target = owner if owner else user_id
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM children WHERE user_id=? ORDER BY birthdate", (target,)
    ).fetchall()
    conn.close()
    return rows


def get_child(child_id, user_id):
    owner = get_family_owner(user_id)
    allowed_ids = [user_id] + ([owner] if owner else [])
    conn = get_conn()
    row = conn.execute(
        f"SELECT * FROM children WHERE id=? AND user_id IN ({','.join('?'*len(allowed_ids))})",
        [child_id] + allowed_ids
    ).fetchone()
    conn.close()
    return row


def add_child(user_id, name, birthdate, gender):
    owner = get_family_owner(user_id)
    target = owner if owner else user_id
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO children (user_id, name, birthdate, gender) VALUES (?,?,?,?)",
        (target, name, birthdate, gender)
    )
    child_id = c.lastrowid
    conn.commit()
    conn.close()
    return child_id


def delete_child(child_id, user_id):
    owner = get_family_owner(user_id)
    allowed_ids = [user_id] + ([owner] if owner else [])
    conn = get_conn()
    conn.execute("DELETE FROM growth_records WHERE child_id=?", (child_id,))
    conn.execute("DELETE FROM vaccinations WHERE child_id=?", (child_id,))
    conn.execute("DELETE FROM photo_diary WHERE child_id=?", (child_id,))
    conn.execute("DELETE FROM medications WHERE child_id=?", (child_id,))
    conn.execute(
        "DELETE FROM illness_entries WHERE illness_id IN (SELECT id FROM illness_log WHERE child_id=?)",
        (child_id,)
    )
    conn.execute("DELETE FROM illness_log WHERE child_id=?", (child_id,))
    conn.execute(
        f"DELETE FROM children WHERE id=? AND user_id IN ({','.join('?'*len(allowed_ids))})",
        [child_id] + allowed_ids
    )
    conn.commit()
    conn.close()


# ── Рост и вес ───────────────────────────────────────────────────────────────

def add_growth_record(user_id, child_id, date, height, weight):
    conn = get_conn()
    conn.execute(
        "INSERT INTO growth_records (child_id, user_id, date, height_cm, weight_kg) VALUES (?,?,?,?,?)",
        (child_id, user_id, date, height, weight)
    )
    conn.commit()
    conn.close()


def get_growth_records(child_id, user_id, limit=100):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM growth_records WHERE child_id=? ORDER BY date DESC LIMIT ?",
        (child_id, limit)
    ).fetchall()
    conn.close()
    return rows


# ── Прививки ─────────────────────────────────────────────────────────────────

def add_vaccination(user_id, child_id, vaccine_name, scheduled_date=None, done_date=None, notes=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO vaccinations (child_id, user_id, vaccine_name, scheduled_date, done_date, notes) VALUES (?,?,?,?,?,?)",
        (child_id, user_id, vaccine_name, scheduled_date, done_date, notes)
    )
    conn.commit()
    conn.close()


def get_vaccinations(child_id, user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM vaccinations WHERE child_id=? ORDER BY scheduled_date",
        (child_id,)
    ).fetchall()
    conn.close()
    return rows


def mark_vaccination_done(vac_id, user_id, done_date):
    conn = get_conn()
    conn.execute(
        "UPDATE vaccinations SET done_date=? WHERE id=?",
        (done_date, vac_id)
    )
    conn.commit()
    conn.close()


# ── Напоминания ──────────────────────────────────────────────────────────────

def add_reminder(user_id, child_id, title, remind_at, repeat_type="none"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO reminders (user_id, child_id, title, remind_at, repeat_type) VALUES (?,?,?,?,?)",
        (user_id, child_id, title, remind_at, repeat_type)
    )
    conn.commit()
    conn.close()


def get_reminders(user_id, active_only=True):
    conn = get_conn()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE user_id=? AND is_active=1 ORDER BY remind_at",
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE user_id=? ORDER BY remind_at",
            (user_id,)
        ).fetchall()
    conn.close()
    return rows


def get_due_reminders():
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = conn.execute(
        "SELECT * FROM reminders WHERE is_active=1 AND remind_at<=?", (now,)
    ).fetchall()
    conn.close()
    return rows


def deactivate_reminder(reminder_id):
    conn = get_conn()
    conn.execute("UPDATE reminders SET is_active=0 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def delete_reminder(reminder_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM reminders WHERE id=? AND user_id=?", (reminder_id, user_id))
    conn.commit()
    conn.close()


# ── Фотодневник ──────────────────────────────────────────────────────────────

def add_photo(user_id, child_id, file_id, caption, photo_date):
    conn = get_conn()
    conn.execute(
        "INSERT INTO photo_diary (user_id, child_id, file_id, caption, photo_date) VALUES (?,?,?,?,?)",
        (user_id, child_id, file_id, caption, photo_date)
    )
    conn.commit()
    conn.close()


def get_photos(child_id, limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM photo_diary WHERE child_id=? ORDER BY photo_date DESC, created_at DESC LIMIT ?",
        (child_id, limit)
    ).fetchall()
    conn.close()
    return rows


def delete_photo(photo_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM photo_diary WHERE id=? AND user_id=?", (photo_id, user_id))
    conn.commit()
    conn.close()


# ── Лекарства ────────────────────────────────────────────────────────────────

def add_medication(user_id, child_id, name, dose, interval_hours, end_date=None):
    next_at = (datetime.now() + timedelta(hours=interval_hours)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO medications (user_id, child_id, name, dose, interval_hours, next_reminder_at, end_date)
           VALUES (?,?,?,?,?,?,?)""",
        (user_id, child_id, name, dose, interval_hours, next_at, end_date)
    )
    med_id = c.lastrowid
    conn.commit()
    conn.close()
    return med_id


def get_medications(child_id, active_only=True):
    conn = get_conn()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM medications WHERE child_id=? AND is_active=1 ORDER BY created_at DESC",
            (child_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM medications WHERE child_id=? ORDER BY created_at DESC",
            (child_id,)
        ).fetchall()
    conn.close()
    return rows


def get_all_active_medications():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM medications WHERE is_active=1"
    ).fetchall()
    conn.close()
    return rows


def update_medication_next_reminder(med_id, interval_hours):
    next_at = (datetime.now() + timedelta(hours=interval_hours)).isoformat()
    conn = get_conn()
    conn.execute(
        "UPDATE medications SET next_reminder_at=? WHERE id=?",
        (next_at, med_id)
    )
    conn.commit()
    conn.close()


def deactivate_medication(med_id, user_id):
    conn = get_conn()
    conn.execute(
        "UPDATE medications SET is_active=0 WHERE id=? AND user_id=?",
        (med_id, user_id)
    )
    conn.commit()
    conn.close()


# ── Журнал болезней ──────────────────────────────────────────────────────────

def start_illness(user_id, child_id, illness_name, start_date):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO illness_log (user_id, child_id, illness_name, start_date) VALUES (?,?,?,?)",
        (user_id, child_id, illness_name, start_date)
    )
    ill_id = c.lastrowid
    conn.commit()
    conn.close()
    return ill_id


def get_illnesses(child_id, active_only=False, limit=10):
    conn = get_conn()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM illness_log WHERE child_id=? AND is_active=1 ORDER BY start_date DESC",
            (child_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM illness_log WHERE child_id=? ORDER BY start_date DESC LIMIT ?",
            (child_id, limit)
        ).fetchall()
    conn.close()
    return rows


def get_illness(illness_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM illness_log WHERE id=?", (illness_id,)).fetchone()
    conn.close()
    return row


def end_illness(illness_id, end_date):
    conn = get_conn()
    conn.execute(
        "UPDATE illness_log SET is_active=0, end_date=? WHERE id=?",
        (end_date, illness_id)
    )
    conn.commit()
    conn.close()


def add_illness_entry(illness_id, entry_date, temperature, symptoms, medications_given, notes):
    conn = get_conn()
    conn.execute(
        """INSERT INTO illness_entries (illness_id, entry_date, temperature, symptoms, medications_given, notes)
           VALUES (?,?,?,?,?,?)""",
        (illness_id, entry_date, temperature, symptoms, medications_given, notes)
    )
    conn.commit()
    conn.close()


def get_illness_entries(illness_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM illness_entries WHERE illness_id=? ORDER BY entry_date, created_at",
        (illness_id,)
    ).fetchall()
    conn.close()
    return rows
