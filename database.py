import os
import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_TZ = ZoneInfo(os.environ.get("BOT_TIMEZONE", "Europe/Moscow"))

DATABASE_URL = os.environ.get("DATABASE_URL")
DB_PATH = os.path.join(os.path.dirname(__file__), "mama_bot.db")


def get_conn():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _is_pg():
    return bool(DATABASE_URL)


def _q(sql):
    """Конвертирует ? в %s для PostgreSQL."""
    if _is_pg():
        return sql.replace("?", "%s")
    return sql


def _fetchone(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    if _is_pg():
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))
    return row


def _fetchall(cursor):
    rows = cursor.fetchall()
    if _is_pg():
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in rows]
    return rows


def init_db():
    conn = get_conn()
    c = conn.cursor()
    pg = _is_pg()

    auto = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    text_default = "TIMESTAMP DEFAULT NOW()" if pg else "TEXT DEFAULT CURRENT_TIMESTAMP"
    int_type = "INTEGER" if not pg else "INTEGER"

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_premium INTEGER DEFAULT 0,
            premium_until TEXT,
            trial_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS family_members (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            owner_user_id BIGINT NOT NULL,
            member_user_id BIGINT NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_user_id, member_user_id)
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS children (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            user_id BIGINT NOT NULL,
            name TEXT NOT NULL,
            birthdate TEXT NOT NULL,
            gender TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS growth_records (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            child_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,
            date TEXT NOT NULL,
            height_cm REAL,
            weight_kg REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS vaccinations (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            child_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,
            vaccine_name TEXT NOT NULL,
            scheduled_date TEXT,
            done_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS reminders (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            user_id BIGINT NOT NULL,
            child_id INTEGER,
            title TEXT NOT NULL,
            remind_at TEXT NOT NULL,
            repeat_type TEXT DEFAULT 'none',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS photo_diary (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            user_id BIGINT NOT NULL,
            child_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            caption TEXT,
            photo_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS medications (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            user_id BIGINT NOT NULL,
            child_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dose TEXT,
            interval_hours REAL NOT NULL,
            next_reminder_at TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS illness_log (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            user_id BIGINT NOT NULL,
            child_id INTEGER NOT NULL,
            illness_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS illness_entries (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            illness_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            temperature REAL,
            symptoms TEXT,
            medications_given TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


    c.execute(f"""
        CREATE TABLE IF NOT EXISTS medical_info (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            child_id INTEGER NOT NULL UNIQUE,
            blood_group TEXT,
            blood_rh TEXT,
            policy_number TEXT,
            policy_company TEXT,
            snils TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS allergies (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            child_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            reaction TEXT,
            severity TEXT DEFAULT 'mild',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS contraindications (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            child_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS referrals (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            referrer_user_id BIGINT NOT NULL,
            referred_user_id BIGINT NOT NULL UNIQUE,
            bonus_given INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    if not pg:
        for migration in [
            "ALTER TABLE users ADD COLUMN trial_used INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN referred_by BIGINT",
        ]:
            try:
                c.execute(migration)
            except Exception:
                pass


    c.execute(f"""
        CREATE TABLE IF NOT EXISTS medical_info (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            child_id INTEGER NOT NULL UNIQUE,
            blood_group TEXT,
            blood_rh TEXT,
            policy_number TEXT,
            policy_company TEXT,
            snils TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS allergies (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            child_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            reaction TEXT,
            severity TEXT DEFAULT 'mild',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS contraindications (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            child_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS referrals (
            id {'SERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            referrer_user_id BIGINT NOT NULL,
            referred_user_id BIGINT NOT NULL UNIQUE,
            bonus_given INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    if not pg:
        for migration in [
            "ALTER TABLE users ADD COLUMN trial_used INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN referred_by BIGINT",
        ]:
            try:
                c.execute(migration)
            except Exception:
                pass

    conn.commit()
    conn.close()


def upsert_user(user_id, username, first_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT user_id FROM users WHERE user_id=?"), (user_id,))
    existing = _fetchone(c)
    is_new = existing is None
    if _is_pg():
        c.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username, first_name=EXCLUDED.first_name
        """, (user_id, username, first_name))
    else:
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
    c = conn.cursor()
    c.execute(_q("SELECT * FROM users WHERE user_id=?"), (user_id,))
    row = _fetchone(c)
    conn.close()
    return row


def activate_trial(user_id):
    user = get_user(user_id)
    if user and user["trial_used"]:
        return None
    until = (datetime.now() + timedelta(days=14)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE users SET is_premium=1, premium_until=?, trial_used=1 WHERE user_id=?"), (until, user_id))
    conn.commit()
    conn.close()
    return until


def set_premium(user_id, until_date: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?"), (until_date, user_id))
    conn.commit()
    conn.close()


def is_premium(user_id):
    if _check_premium_direct(user_id):
        return True
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT owner_user_id FROM family_members WHERE member_user_id=?"), (user_id,))
    owners = _fetchall(c)
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
            c = conn.cursor()
            c.execute(_q("UPDATE users SET is_premium=0 WHERE user_id=?"), (user_id,))
            conn.commit()
            conn.close()
            return False
    return True


def revoke_premium(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE users SET is_premium=0, premium_until=NULL WHERE user_id=?"), (user_id,))
    conn.commit()
    conn.close()


# ── Семейный доступ ──────────────────────────────────────────────────────────

def add_family_member(owner_user_id, member_user_id):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(_q("INSERT INTO family_members (owner_user_id, member_user_id) VALUES (?,?)"),
                  (owner_user_id, member_user_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False


def remove_family_member(owner_user_id, member_user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("DELETE FROM family_members WHERE owner_user_id=? AND member_user_id=?"),
              (owner_user_id, member_user_id))
    conn.commit()
    conn.close()


def get_family_members(owner_user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("""SELECT fm.member_user_id, u.username, u.first_name
               FROM family_members fm
               LEFT JOIN users u ON u.user_id = fm.member_user_id
               WHERE fm.owner_user_id=?"""), (owner_user_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def get_family_owner(member_user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT owner_user_id FROM family_members WHERE member_user_id=?"), (member_user_id,))
    row = _fetchone(c)
    conn.close()
    return row["owner_user_id"] if row else None


# ── Дети ─────────────────────────────────────────────────────────────────────

def get_children(user_id):
    owner = get_family_owner(user_id)
    target = owner if owner else user_id
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM children WHERE user_id=? ORDER BY birthdate"), (target,))
    rows = _fetchall(c)
    conn.close()
    return rows


def get_child(child_id, user_id):
    owner = get_family_owner(user_id)
    allowed_ids = [user_id] + ([owner] if owner else [])
    conn = get_conn()
    c = conn.cursor()
    placeholders = ",".join(["%s" if _is_pg() else "?"] * len(allowed_ids))
    c.execute(f"SELECT * FROM children WHERE id={'%s' if _is_pg() else '?'} AND user_id IN ({placeholders})",
              [child_id] + allowed_ids)
    row = _fetchone(c)
    conn.close()
    return row


def add_child(user_id, name, birthdate, gender):
    owner = get_family_owner(user_id)
    target = owner if owner else user_id
    conn = get_conn()
    c = conn.cursor()
    if _is_pg():
        c.execute("INSERT INTO children (user_id, name, birthdate, gender) VALUES (%s,%s,%s,%s) RETURNING id",
                  (target, name, birthdate, gender))
        child_id = c.fetchone()[0]
    else:
        c.execute("INSERT INTO children (user_id, name, birthdate, gender) VALUES (?,?,?,?)",
                  (target, name, birthdate, gender))
        child_id = c.lastrowid
    conn.commit()
    conn.close()
    return child_id


def delete_child(child_id, user_id):
    owner = get_family_owner(user_id)
    allowed_ids = [user_id] + ([owner] if owner else [])
    conn = get_conn()
    c = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    c.execute(_q("DELETE FROM growth_records WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM vaccinations WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM photo_diary WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM medications WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM illness_entries WHERE illness_id IN (SELECT id FROM illness_log WHERE child_id=?)"), (child_id,))
    c.execute(_q("DELETE FROM illness_log WHERE child_id=?"), (child_id,))
    placeholders = ",".join([ph] * len(allowed_ids))
    c.execute(f"DELETE FROM children WHERE id={ph} AND user_id IN ({placeholders})", [child_id] + allowed_ids)
    conn.commit()
    conn.close()


# ── Рост и вес ───────────────────────────────────────────────────────────────

def add_growth_record(user_id, child_id, date, height, weight):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("INSERT INTO growth_records (child_id, user_id, date, height_cm, weight_kg) VALUES (?,?,?,?,?)"),
              (child_id, user_id, date, height, weight))
    conn.commit()
    conn.close()


def get_growth_records(child_id, user_id, limit=100):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM growth_records WHERE child_id=? ORDER BY date DESC LIMIT ?"), (child_id, limit))
    rows = _fetchall(c)
    conn.close()
    return rows


# ── Прививки ─────────────────────────────────────────────────────────────────

def add_vaccination(user_id, child_id, vaccine_name, scheduled_date=None, done_date=None, notes=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("INSERT INTO vaccinations (child_id, user_id, vaccine_name, scheduled_date, done_date, notes) VALUES (?,?,?,?,?,?)"),
              (child_id, user_id, vaccine_name, scheduled_date, done_date, notes))
    conn.commit()
    conn.close()


def get_vaccinations(child_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM vaccinations WHERE child_id=? ORDER BY scheduled_date"), (child_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def mark_vaccination_done(vac_id, user_id, done_date):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE vaccinations SET done_date=? WHERE id=?"), (done_date, vac_id))
    conn.commit()
    conn.close()


# ── Напоминания ──────────────────────────────────────────────────────────────

def add_reminder(user_id, child_id, title, remind_at, repeat_type="none"):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("INSERT INTO reminders (user_id, child_id, title, remind_at, repeat_type) VALUES (?,?,?,?,?)"),
              (user_id, child_id, title, remind_at, repeat_type))
    conn.commit()
    conn.close()


def get_reminders(user_id, active_only=True):
    conn = get_conn()
    c = conn.cursor()
    if active_only:
        c.execute(_q("SELECT * FROM reminders WHERE user_id=? AND is_active=1 ORDER BY remind_at"), (user_id,))
    else:
        c.execute(_q("SELECT * FROM reminders WHERE user_id=? ORDER BY remind_at"), (user_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def get_due_reminders(now_str: str = None):
    conn = get_conn()
    c = conn.cursor()
    if now_str is None:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute(_q("SELECT * FROM reminders WHERE is_active=1 AND remind_at<=?"), (now_str,))
    rows = _fetchall(c)
    conn.close()
    return rows


def deactivate_reminder(reminder_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE reminders SET is_active=0 WHERE id=?"), (reminder_id,))
    conn.commit()
    conn.close()


def delete_reminder(reminder_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("DELETE FROM reminders WHERE id=? AND user_id=?"), (reminder_id, user_id))
    conn.commit()
    conn.close()


# ── Фотодневник ──────────────────────────────────────────────────────────────

def add_photo(user_id, child_id, file_id, caption, photo_date):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("INSERT INTO photo_diary (user_id, child_id, file_id, caption, photo_date) VALUES (?,?,?,?,?)"),
              (user_id, child_id, file_id, caption, photo_date))
    conn.commit()
    conn.close()


def get_photos(child_id, limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM photo_diary WHERE child_id=? ORDER BY photo_date DESC, created_at DESC LIMIT ?"),
              (child_id, limit))
    rows = _fetchall(c)
    conn.close()
    return rows


def delete_photo(photo_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("DELETE FROM photo_diary WHERE id=? AND user_id=?"), (photo_id, user_id))
    conn.commit()
    conn.close()


# ── Лекарства ────────────────────────────────────────────────────────────────

def add_medication(user_id, child_id, name, dose, interval_hours, end_date=None):
    next_at = (datetime.now(_TZ) + timedelta(hours=interval_hours)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    if _is_pg():
        c.execute("""INSERT INTO medications (user_id, child_id, name, dose, interval_hours, next_reminder_at, end_date)
                     VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                  (user_id, child_id, name, dose, interval_hours, next_at, end_date))
        med_id = c.fetchone()[0]
    else:
        c.execute("""INSERT INTO medications (user_id, child_id, name, dose, interval_hours, next_reminder_at, end_date)
                     VALUES (?,?,?,?,?,?,?)""",
                  (user_id, child_id, name, dose, interval_hours, next_at, end_date))
        med_id = c.lastrowid
    conn.commit()
    conn.close()
    return med_id


def get_medications(child_id, active_only=True):
    conn = get_conn()
    c = conn.cursor()
    if active_only:
        c.execute(_q("SELECT * FROM medications WHERE child_id=? AND is_active=1 ORDER BY created_at DESC"), (child_id,))
    else:
        c.execute(_q("SELECT * FROM medications WHERE child_id=? ORDER BY created_at DESC"), (child_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def get_all_active_medications():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM medications WHERE is_active=1")
    rows = _fetchall(c)
    conn.close()
    return rows


def update_medication_next_reminder(med_id, interval_hours):
    next_at = (datetime.now(_TZ) + timedelta(hours=interval_hours)).isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE medications SET next_reminder_at=? WHERE id=?"), (next_at, med_id))
    conn.commit()
    conn.close()


def deactivate_medication(med_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE medications SET is_active=0 WHERE id=? AND user_id=?"), (med_id, user_id))
    conn.commit()
    conn.close()


# ── Журнал болезней ──────────────────────────────────────────────────────────

def start_illness(user_id, child_id, illness_name, start_date):
    conn = get_conn()
    c = conn.cursor()
    if _is_pg():
        c.execute("INSERT INTO illness_log (user_id, child_id, illness_name, start_date) VALUES (%s,%s,%s,%s) RETURNING id",
                  (user_id, child_id, illness_name, start_date))
        ill_id = c.fetchone()[0]
    else:
        c.execute("INSERT INTO illness_log (user_id, child_id, illness_name, start_date) VALUES (?,?,?,?)",
                  (user_id, child_id, illness_name, start_date))
        ill_id = c.lastrowid
    conn.commit()
    conn.close()
    return ill_id


def get_illnesses(child_id, active_only=False, limit=10):
    conn = get_conn()
    c = conn.cursor()
    if active_only:
        c.execute(_q("SELECT * FROM illness_log WHERE child_id=? AND is_active=1 ORDER BY start_date DESC"), (child_id,))
    else:
        c.execute(_q("SELECT * FROM illness_log WHERE child_id=? ORDER BY start_date DESC LIMIT ?"), (child_id, limit))
    rows = _fetchall(c)
    conn.close()
    return rows


def get_illness(illness_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM illness_log WHERE id=?"), (illness_id,))
    row = _fetchone(c)
    conn.close()
    return row


def end_illness(illness_id, end_date):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE illness_log SET is_active=0, end_date=? WHERE id=?"), (end_date, illness_id))
    conn.commit()
    conn.close()


def add_illness_entry(illness_id, entry_date, temperature, symptoms, medications_given, notes):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("""INSERT INTO illness_entries (illness_id, entry_date, temperature, symptoms, medications_given, notes)
                    VALUES (?,?,?,?,?,?)"""),
              (illness_id, entry_date, temperature, symptoms, medications_given, notes))
    conn.commit()
    conn.close()


def get_illness_entries(illness_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM illness_entries WHERE illness_id=? ORDER BY entry_date, created_at"), (illness_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


# ── Статистика ───────────────────────────────────────────────────────────────

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = _fetchall(c)
    conn.close()
    return rows


# ── Медицинская информация ────────────────────────────────────────────────────

def get_medical_info(child_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM medical_info WHERE child_id=?"), (child_id,))
    row = _fetchone(c)
    conn.close()
    return row


def set_medical_info(child_id, blood_group=None, blood_rh=None,
                     policy_number=None, policy_company=None, snils=None):
    conn = get_conn()
    c = conn.cursor()
    existing = None
    c.execute(_q("SELECT id FROM medical_info WHERE child_id=?"), (child_id,))
    existing = _fetchone(c)

    if existing:
        fields, vals = [], []
        if blood_group  is not None: fields.append("blood_group=?");    vals.append(blood_group)
        if blood_rh     is not None: fields.append("blood_rh=?");       vals.append(blood_rh)
        if policy_number is not None: fields.append("policy_number=?"); vals.append(policy_number)
        if policy_company is not None: fields.append("policy_company=?"); vals.append(policy_company)
        if snils        is not None: fields.append("snils=?");           vals.append(snils)
        if fields:
            vals.append(child_id)
            c.execute(_q(f"UPDATE medical_info SET {', '.join(fields)} WHERE child_id=?"), vals)
    else:
        if _is_pg():
            c.execute(
                "INSERT INTO medical_info (child_id, blood_group, blood_rh, policy_number, policy_company, snils) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (child_id, blood_group, blood_rh, policy_number, policy_company, snils)
            )
        else:
            c.execute(
                "INSERT INTO medical_info (child_id, blood_group, blood_rh, policy_number, policy_company, snils) "
                "VALUES (?,?,?,?,?,?)",
                (child_id, blood_group, blood_rh, policy_number, policy_company, snils)
            )
    conn.commit()
    conn.close()


# ── Аллергии ─────────────────────────────────────────────────────────────────

def add_allergy(child_id, name, reaction="", severity="mild"):
    conn = get_conn()
    c = conn.cursor()
    if _is_pg():
        c.execute(
            "INSERT INTO allergies (child_id, name, reaction, severity) VALUES (%s,%s,%s,%s)",
            (child_id, name, reaction, severity)
        )
    else:
        c.execute(
            "INSERT INTO allergies (child_id, name, reaction, severity) VALUES (?,?,?,?)",
            (child_id, name, reaction, severity)
        )
    conn.commit()
    conn.close()


def get_allergies(child_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM allergies WHERE child_id=? ORDER BY severity DESC"), (child_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def delete_allergy(allergy_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT child_id FROM allergies WHERE id=?"), (allergy_id,))
    row = _fetchone(c)
    child_id = row["child_id"] if row else None
    c.execute(_q("DELETE FROM allergies WHERE id=?"), (allergy_id,))
    conn.commit()
    conn.close()
    return child_id


# ── Противопоказания ──────────────────────────────────────────────────────────

def add_contraindication(child_id, name):
    conn = get_conn()
    c = conn.cursor()
    if _is_pg():
        c.execute("INSERT INTO contraindications (child_id, name) VALUES (%s,%s)", (child_id, name))
    else:
        c.execute("INSERT INTO contraindications (child_id, name) VALUES (?,?)", (child_id, name))
    conn.commit()
    conn.close()


def get_contraindications(child_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM contraindications WHERE child_id=? ORDER BY created_at"), (child_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def delete_contraindication(contra_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT child_id FROM contraindications WHERE id=?"), (contra_id,))
    row = _fetchone(c)
    child_id = row["child_id"] if row else None
    c.execute(_q("DELETE FROM contraindications WHERE id=?"), (contra_id,))
    conn.commit()
    conn.close()
    return child_id


# ── Реферальная система ───────────────────────────────────────────────────────

def get_referral_code(user_id):
    """Реферальный код = просто ID пользователя."""
    return str(user_id)


def apply_referral(referred_user_id, referrer_user_id):
    """Записывает реферала. Возвращает True если успешно."""
    if referred_user_id == referrer_user_id:
        return False
    conn = get_conn()
    c = conn.cursor()
    # Проверяем что пользователь ещё не был приглашён
    c.execute(_q("SELECT id FROM referrals WHERE referred_user_id=?"), (referred_user_id,))
    if _fetchone(c):
        conn.close()
        return False
    if _is_pg():
        c.execute(
            "INSERT INTO referrals (referrer_user_id, referred_user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (referrer_user_id, referred_user_id)
        )
    else:
        c.execute(
            "INSERT OR IGNORE INTO referrals (referrer_user_id, referred_user_id) VALUES (?,?)",
            (referrer_user_id, referred_user_id)
        )
    conn.commit()
    conn.close()
    return True


def give_referral_bonus(referrer_user_id, bonus_days=7):
    """Даёт бонус пригласившему."""
    from datetime import datetime, timedelta
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT premium_until, is_premium FROM users WHERE user_id=?"), (referrer_user_id,))
    row = _fetchone(c)
    if not row:
        conn.close()
        return

    now = datetime.now()
    if row["is_premium"] and row["premium_until"]:
        try:
            base = datetime.fromisoformat(row["premium_until"])
            if base < now:
                base = now
        except Exception:
            base = now
    else:
        base = now

    until = (base + timedelta(days=bonus_days)).isoformat()
    if _is_pg():
        c.execute(
            "UPDATE users SET is_premium=1, premium_until=%s WHERE user_id=%s",
            (until, referrer_user_id)
        )
    else:
        c.execute(
            "UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?",
            (until, referrer_user_id)
        )
    # Отмечаем что бонус выдан
    c.execute(
        _q("UPDATE referrals SET bonus_given=1 WHERE referrer_user_id=? AND bonus_given=0"),
        (referrer_user_id,)
    )
    conn.commit()
    conn.close()
    return until


def get_referral_stats(user_id):
    """Статистика рефералов пользователя."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_user_id=?"), (user_id,))
    row = _fetchone(c)
    total = row["cnt"] if row else 0
    c.execute(_q("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_user_id=? AND bonus_given=1"), (user_id,))
    row2 = _fetchone(c)
    bonused = row2["cnt"] if row2 else 0
    conn.close()
    return {"total": total, "bonused": bonused}
