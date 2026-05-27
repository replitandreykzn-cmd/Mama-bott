import os
import psycopg2
import psycopg2.extras
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
        return sql.replace(\"?\", \"%s\")
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
        return [dict(zip(cols, row)) for row in rows]\
    return rows


def init_db():
    conn = get_conn()
    c = conn.cursor()
    pg = _is_pg()

    auto_inc = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    text_type = "TEXT"

    # Таблица пользователей
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username {text_type},
            first_name {text_type},
            created_at {text_type},
            premium_until {text_type}
        )
    """)

    # Таблица детей
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS children (
            id {auto_inc},
            user_id BIGINT,
            name {text_type},
            birthdate {text_type},
            gender {text_type}
        )
    """)

    # Таблица роста и веса
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS growth (
            id {auto_inc},
            child_id INTEGER,
            user_id BIGINT,
            rec_date {text_type},
            height REAL,
            weight REAL
        )
    """)

    # Таблица вакцинации
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS vaccinations (
            id {auto_inc},
            child_id INTEGER,
            vaccine_name {text_type},
            scheduled_date {text_type},
            done_date {text_type}
        )
    """)

    # Таблица напоминаний
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS reminders (
            id {auto_inc},
            user_id BIGINT,
            title {text_type},
            remind_at {text_type},
            is_active INTEGER DEFAULT 1
        )
    """)

    # Таблица лекарств
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS medications (
            id {auto_inc},
            child_id INTEGER,
            user_id BIGINT,
            name {text_type},
            dose {text_type},
            interval_hours INTEGER,
            end_date {text_type},
            next_remind {text_type},
            is_active INTEGER DEFAULT 1
        )
    """)

    # Таблица болезней
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS illnesses (
            id {auto_inc},
            child_id INTEGER,
            illness_name {text_type},
            start_date {text_type},
            end_date {text_type},
            temperature {text_type},
            symptoms {text_type},
            medications {text_type},
            notes {text_type},
            is_active INTEGER DEFAULT 1
        )
    """)

    # Таблица медкарты
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS medical_info (
            child_id INTEGER PRIMARY KEY,
            blood_group {text_type},
            blood_rh {text_type},
            policy_number {text_type},
            policy_company {text_type},
            snils {text_type}
        )
    """)

    # Таблица аллергий
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS allergies (
            id {auto_inc},
            child_id INTEGER,
            name {text_type},
            reaction {text_type},
            severity {text_type}
        )
    """)

    # Таблица противопоказаний
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS contraindications (
            id {auto_inc},
            child_id INTEGER,
            name {text_type}
        )
    """)

    # Таблица рефералов
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS referrals (
            id {auto_inc},
            referrer_user_id BIGINT,
            referred_user_id BIGINT UNIQUE,
            bonus_given INTEGER DEFAULT 0
        )
    """)

    # Таблица семейного доступа
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS family_access (
            id {auto_inc},
            owner_user_id BIGINT,
            member_user_id BIGINT,
            PRIMARY KEY (owner_user_id, member_user_id)
        )
    """)

    # Пройденные осмотры
    if pg:
        c.execute("""
            CREATE TABLE IF NOT EXISTS checkups_done (
                child_id INTEGER,
                checkup_months INTEGER,
                done_date TEXT,
                PRIMARY KEY (child_id, checkup_months)
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS checkups_done (
                child_id INTEGER,
                checkup_months INTEGER,
                done_date TEXT,
                PRIMARY KEY (child_id, checkup_months)
            )
        """)

    conn.commit()
    conn.close()


# ── Функции пользователей ───────────────────────────────────────────────────

def add_user(user_id, username, first_name):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now(_TZ).isoformat()
    if _is_pg():
        c.execute(
            "INSERT INTO users (user_id, username, first_name, created_at) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (user_id) DO NOTHING",
            (user_id, username, first_name, now)
        )
    else:
        c.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, created_at) VALUES (?,?,?,?)",
            (user_id, username, first_name, now)
        )
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM users WHERE user_id=?"), (user_id,))
    row = _fetchone(c)
    conn.close()
    return row


def is_premium(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT premium_until FROM users WHERE user_id=?"), (user_id,))
    row = _fetchone(c)
    conn.close()
    if not row or not row["premium_until"]:
        return False
    try:
        until = datetime.fromisoformat(row["premium_until"])
        return until > datetime.now()
    except Exception:
        return False


def set_premium(user_id, until_iso):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE users SET premium_until=? WHERE user_id=?"), (until_iso, user_id))
    conn.commit()
    conn.close()


def get_premium_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, premium_until FROM users WHERE premium_until IS NOT NULL")
    rows = _fetchall(c)
    conn.close()
    return rows


# ── Функции детей ───────────────────────────────────────────────────────────

def add_child(user_id, name, birthdate, gender):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        _q("INSERT INTO children (user_id, name, birthdate, gender) VALUES (?,?,?,?)"),
        (user_id, name, birthdate, gender)
    )
    conn.commit()
    conn.close()


def get_children(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM children WHERE user_id=? ORDER BY id"), (user_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def get_child(child_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM children WHERE id=? AND user_id=?"), (child_id, user_id))
    row = _fetchone(c)
    conn.close()
    return row


def delete_child(child_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("DELETE FROM children WHERE id=? AND user_id=?"), (child_id, user_id))
    c.execute(_q("DELETE FROM growth WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM vaccinations WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM checkups_done WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM medical_info WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM allergies WHERE child_id=?"), (child_id,))
    c.execute(_q("DELETE FROM contraindications WHERE child_id=?"), (child_id,))
    conn.commit()
    conn.close()


def get_all_children_raw():
    """Возвращает список всех детей из базы данных для фоновой рассылки."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, user_id, name, birthdate, gender FROM children")
    rows = _fetchall(c)
    conn.close()
    return rows


# ── Рост и вес ──────────────────────────────────────────────────────────────

def add_growth_record(user_id, child_id, rec_date, height, weight):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        _q("INSERT INTO growth (user_id, child_id, rec_date, height, weight) VALUES (?,?,?,?,?)"),
        (user_id, child_id, rec_date, height, weight)
    )
    conn.commit()
    conn.close()


def get_growth_records(child_id, user_id, limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        _q("SELECT * FROM growth WHERE child_id=? AND user_id=? ORDER BY id DESC LIMIT ?"),
        (child_id, user_id, limit)
    )
    rows = _fetchall(c)
    conn.close()
    return rows


# ── Вакцинация ──────────────────────────────────────────────────────────────

def add_vaccination_schedule(child_id, schedule_list):
    conn = get_conn()
    c = conn.cursor()
    for name, s_date in schedule_list:
        c.execute(
            _q("INSERT INTO vaccinations (child_id, vaccine_name, scheduled_date) VALUES (?,?,?)"),
            (child_id, name, s_date)
        )
    conn.commit()
    conn.close()


def get_vaccinations(child_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        _q("SELECT v.* FROM vaccinations v JOIN children ch ON v.child_id=ch.id WHERE v.child_id=? AND ch.user_id=? ORDER BY v.id"),
        (child_id, user_id)
    )
    rows = _fetchall(c)
    conn.close()
    return rows


def mark_vaccination_done(vac_id, user_id, done_date):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        _q("UPDATE vaccinations SET done_date=? WHERE id=? AND child_id IN (SELECT id FROM children WHERE user_id=?)"),
        (done_date, vac_id, user_id)
    )
    conn.commit()
    conn.close()


def get_weekly_pending_vaccines():
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now(_TZ).date()
    next_week = today + timedelta(days=7)
    
    sql = "SELECT v.id, v.vaccine_name, v.scheduled_date, ch.name as child_name, ch.user_id, ch.gender FROM vaccinations v JOIN children ch ON v.child_id=ch.id WHERE v.done_date IS NULL"
    c.execute(sql)
    rows = _fetchall(c)
    conn.close()

    urgent = []
    for r in rows:
        if not r["scheduled_date"]:
            continue
        try:
            d = datetime.strptime(r["scheduled_date"], "%d.%m.%Y").date()
            if today <= d <= next_week:
                urgent.append(r)
        except Exception:
            pass
    return urgent


# ── Напоминания ─────────────────────────────────────────────────────────────

def add_reminder(user_id, title, remind_at_iso):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        _q("INSERT INTO reminders (user_id, title, remind_at) VALUES (?,?,?)"),
        (user_id, title, remind_at_iso)
    )
    conn.commit()
    conn.close()


def get_reminders(user_id, active_only=True):
    conn = get_conn()
    c = conn.cursor()
    if active_only:
        c.execute(_q("SELECT * FROM reminders WHERE user_id=? AND is_active=1 ORDER BY remind_at"), (user_id,))
    else:
        c.execute(_q("SELECT * FROM reminders WHERE user_id=? ORDER BY remind_at DESC"), (user_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def delete_reminder(reminder_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("DELETE FROM reminders WHERE id=? AND user_id=?"), (reminder_id, user_id))
    conn.commit()
    conn.close()


def get_due_reminders():
    conn = get_conn()
    c = conn.cursor()
    now_iso = datetime.now(_TZ).isoformat()
    c.execute(_q("SELECT * FROM reminders WHERE is_active=1 AND remind_at<=?"), (now_iso,))
    rows = _fetchall(c)
    conn.close()
    return rows


def deactivate_reminder(reminder_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE reminders SET is_active=0 WHERE id=?"), (reminder_id,))
    conn.commit()
    conn.close()


# ── Лекарства ───────────────────────────────────────────────────────────────

def add_medication(child_id, user_id, name, dose, interval_hours, end_date_str, next_remind_iso):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        _q("INSERT INTO medications (child_id, user_id, name, dose, interval_hours, end_date, next_remind) VALUES (?,?,?,?,?,?,?)"),
        (child_id, user_id, name, dose, interval_hours, end_date_str, next_remind_iso)
    )
    conn.commit()
    conn.close()


def get_medications(child_id, active_only=True):
    conn = get_conn()
    c = conn.cursor()
    if active_only:
        c.execute(_q("SELECT * FROM medications WHERE child_id=? AND is_active=1 ORDER BY id"), (child_id,))
    else:
        c.execute(_q("SELECT * FROM medications WHERE child_id=? ORDER BY id DESC"), (child_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def deactivate_medication(med_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE medications SET is_active=0 WHERE id=? AND user_id=?"), (med_id, user_id))
    conn.commit()
    conn.close()


def get_due_medications():
    conn = get_conn()
    c = conn.cursor()
    now_iso = datetime.now(_TZ).isoformat()
    c.execute(_q("SELECT m.*, ch.name as child_name, ch.gender FROM medications m JOIN children ch ON m.child_id=ch.id WHERE m.is_active=1 AND m.next_remind<=?"), (now_iso,))
    rows = _fetchall(c)
    conn.close()
    return rows


def update_medication_next_remind(med_id, next_iso, is_active=1):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE medications SET next_remind=?, is_active=? WHERE id=?"), (next_iso, is_active, med_id))
    conn.commit()
    conn.close()


# ── Болезни ─────────────────────────────────────────────────────────────────

def add_illness(child_id, name, start_date, temp, symptoms, meds, notes):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        _q("INSERT INTO illnesses (child_id, illness_name, start_date, temperature, symptoms, medications, notes) VALUES (?,?,?,?,?,?,?)"),
        (child_id, name, start_date, temp, symptoms, meds, notes)
    )
    conn.commit()
    conn.close()


def get_illnesses(child_id, active_only=True, limit=10):
    conn = get_conn()
    c = conn.cursor()
    if active_only:
        c.execute(_q("SELECT * FROM illnesses WHERE child_id=? AND is_active=1 ORDER BY id DESC"), (child_id,))
    else:
        c.execute(_q("SELECT * FROM illnesses WHERE child_id=? ORDER BY id DESC LIMIT ?"), (child_id, limit))
    rows = _fetchall(c)
    conn.close()
    return rows


def close_illness(illness_id, end_date):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("UPDATE illnesses SET is_active=0, end_date=? WHERE id=?"), (end_date, illness_id))
    conn.commit()
    conn.close()


# ── Медкарта ─────────────────────────────────────────────────────────────────

def update_medical_base(child_id, blood_group=None, blood_rh=None, policy_number=None, policy_company=None, snils=None):
    conn = get_conn()
    c = conn.cursor()
    if _is_pg():
        c.execute("INSERT INTO medical_info (child_id) VALUES (%s) ON CONFLICT (child_id) DO NOTHING", (child_id,))
    else:
        c.execute("INSERT OR IGNORE INTO medical_info (child_id) VALUES (?)", (child_id,))
    
    if blood_group: c.execute(_q("UPDATE medical_info SET blood_group=? WHERE child_id=?"), (blood_group, child_id))
    if blood_rh:    c.execute(_q("UPDATE medical_info SET blood_rh=? WHERE child_id=?"), (blood_rh, child_id))
    if policy_number:c.execute(_q("UPDATE medical_info SET policy_number=? WHERE child_id=?"), (policy_number, child_id))
    if policy_company:c.execute(_q("UPDATE medical_info SET policy_company=? WHERE child_id=?"), (policy_company, child_id))
    if snils:        c.execute(_q("UPDATE medical_info SET snils=? WHERE child_id=?"), (snils, child_id))
    
    conn.commit()
    conn.close()


def get_medical_info(child_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM medical_info WHERE child_id=?"), (child_id,))
    row = _fetchone(c)
    conn.close()
    return row


def add_allergy(child_id, name, reaction, severity):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("INSERT INTO allergies (child_id, name, reaction, severity) VALUES (?,?,?,?)"), (child_id, name, reaction, severity))
    conn.commit()
    conn.close()


def get_allergies(child_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM allergies WHERE child_id=? ORDER BY id"), (child_id,))
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


def add_contraindication(child_id, name):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("INSERT INTO contraindications (child_id, name) VALUES (?,?)"), (child_id, name))
    conn.commit()
    conn.close()


def get_contraindications(child_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT * FROM contraindications WHERE child_id=? ORDER BY id"), (child_id,))
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


# ── Семейный доступ ─────────────────────────────────────────────────────────

def add_family_member(owner_id, member_id):
    conn = get_conn()
    c = conn.cursor()
    try:
        if _is_pg():
            c.execute("INSERT INTO family_access (owner_user_id, member_user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (owner_id, member_id))
        else:
            c.execute("INSERT OR IGNORE INTO family_access (owner_user_id, member_user_id) VALUES (?,?)", (owner_id, member_id))
        conn.commit()
        success = True
    except Exception:
        success = False
    conn.close()
    return success


def get_family_members(owner_id):
    conn = get_conn()
    c = conn.cursor()
    sql = "SELECT f.member_user_id, u.first_name, u.username FROM family_access f LEFT JOIN users u ON f.member_user_id=u.user_id WHERE f.owner_user_id=?"
    c.execute(_q(sql), (owner_id,))
    rows = _fetchall(c)
    conn.close()
    return rows


def remove_family_member(owner_id, member_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("DELETE FROM family_access WHERE owner_user_id=? AND member_user_id=?"), (owner_id, member_id))
    conn.commit()
    conn.close()


def get_family_user_ids(user_id):
    """Возвращает список всех ID (самого пользователя + членов его семьи)."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT member_user_id FROM family_access WHERE owner_user_id=?"), (user_id,))
    rows = _fetchall(c)
    
    c.execute(_q("SELECT owner_user_id FROM family_access WHERE member_user_id=?"), (user_id,))
    rows2 = _fetchall(c)
    conn.close()

    res = {user_id}
    for r in rows: res.add(r["member_user_id"])
    for r in rows2: res.add(r["owner_user_id"])
    return list(res)


# ── Рефералы ────────────────────────────────────────────────────────────────

def get_referral_code(user_id):
    return str(user_id)


def apply_referral(referred_id, referrer_id):
    if referred_id == referrer_id:
        return False
    conn = get_conn()
    c = conn.cursor()
    try:
        if _is_pg():
            c.execute("INSERT INTO referrals (referrer_user_id, referred_user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (referrer_id, referred_id))
        else:
            c.execute("INSERT OR IGNORE INTO referrals (referrer_user_id, referred_user_id) VALUES (?,?)", (referrer_id, referred_id))
        conn.commit()
        success = True
    except Exception:
        success = False
    conn.close()
    return success


def give_referral_bonus(referrer_id, days):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT premium_until FROM users WHERE user_id=?"), (referrer_id,))
    row = _fetchone(c)
    if not row:
        conn.close()
        return None

    now = datetime.now()
    current_until = None
    if row["premium_until"]:
        try:
            current_until = datetime.fromisoformat(row["premium_until"])
        except Exception:
            pass

    base_date = current_until if (current_until and current_until > now) else now
    new_until = (base_date + timedelta(days=days)).isoformat()

    c.execute(_q("UPDATE users SET premium_until=? WHERE user_id=?"), (new_until, referrer_id))
    c.execute(_q("UPDATE referrals SET bonus_given=1 WHERE referrer_user_id=? AND bonus_given=0"), (referrer_id,))
    conn.commit()
    conn.close()
    return new_until


def get_referral_stats(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_user_id=?"), (user_id,))
    row1 = _fetchone(c)
    total = row1["cnt"] if row1 else 0

    c.execute(_q("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_user_id=? AND bonus_given=1"), (user_id,))
    row2 = _fetchone(c)
    bonused = row2["cnt"] if row2 else 0
    conn.close()
    return {"total": total, "bonused": bonused}


# ── Пройденные осмотры ────────────────────────────────────────────────────────

def mark_checkup_done(child_id, checkup_months):
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%d.%m.%Y")
    if _is_pg():
        c.execute(
            "INSERT INTO checkups_done (child_id, checkup_months, done_date) "
            "VALUES (%s,%s,%s) ON CONFLICT (child_id, checkup_months) DO UPDATE SET done_date=%s",
            (child_id, checkup_months, today, today)
        )
    else:
        c.execute(
            "INSERT OR REPLACE INTO checkups_done (child_id, checkup_months, done_date) VALUES (?,?,?)",
            (child_id, checkup_months, today)
        )
    conn.commit()
    conn.close()


def get_checkups_done(child_id):
    """Возвращает set месяцев пройденных осмотров."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(_q("SELECT checkup_months FROM checkups_done WHERE child_id=?"), (child_id,))
    rows = _fetchall(c)
    conn.close()
    return set(r["checkup_months"] for r in rows)
