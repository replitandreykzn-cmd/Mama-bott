from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, date
import database as db

CHILD_NAME, CHILD_DATE, CHILD_GENDER = range(3)


def age_str(birthdate_str: str) -> str:
    try:
        bd = datetime.strptime(birthdate_str, "%d.%m.%Y").date()
    except Exception:
        try:
            bd = date.fromisoformat(birthdate_str)
        except Exception:
            return ""
    today = date.today()
    months = (today.year - bd.year) * 12 + today.month - bd.month
    if today.day < bd.day:
        months -= 1
    if months < 0:
        months = 0
    if months < 12:
        return f"{months} мес."
    years = months // 12
    rem = months % 12
    if rem == 0:
        return f"{years} лет"
    return f"{years} л. {rem} мес."


async def show_children_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    children = db.get_children(user_id)
    premium = db.is_premium(user_id)

    keyboard = []
    for ch in children:
        age = age_str(ch["birthdate"])
        emoji = "👧" if ch["gender"] == "girl" else "👦"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {ch['name']} · {age}",
            callback_data=f"child_view:{ch['id']}"
        )])

    can_add = premium or len(children) < 1
    if can_add:
        keyboard.append([InlineKeyboardButton("➕ Добавить ребёнка", callback_data="child_add")])
    else:
        keyboard.append([InlineKeyboardButton("🔒 Добавить ребёнка (Premium)", callback_data="goto_subscription")])

    text = "👶 *Мои дети*\n\nВыберите ребёнка или добавьте нового:"
    if not children:
        text = "👶 *Мои дети*\n\nУ вас пока нет добавленных детей.\nНажмите кнопку ниже, чтобы добавить!"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_child_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная страница ребёнка — показывает всю ключевую информацию сразу."""
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return

    emoji = "👧" if ch["gender"] == "girl" else "👦"
    age = age_str(ch["birthdate"])
    gender_str = "Девочка" if ch["gender"] == "girl" else "Мальчик"

    # ── Последний замер роста/веса ─────────────────────────────────────
    growth = db.get_growth_records(child_id, user_id, limit=1)
    growth_str = "—"
    if growth:
        last = growth[0]
        parts = []
        if last["height_cm"]:
            parts.append(f"{last['height_cm']} см")
        if last["weight_kg"]:
            parts.append(f"{last['weight_kg']} кг")
        if parts:
            growth_str = ", ".join(parts) + f" ({last['date']})"

    # ── Ближайшая прививка ─────────────────────────────────────────────
    vaccines = db.get_vaccinations(child_id, user_id)
    next_vaccine_str = "—"
    for v in vaccines:
        if not v["done_date"] and v["scheduled_date"]:
            try:
                d = datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date()
                days_left = (d - date.today()).days
                if days_left >= 0:
                    if days_left == 0:
                        next_vaccine_str = f"Сегодня! — {v['vaccine_name']}"
                    elif days_left <= 7:
                        next_vaccine_str = f"Через {days_left} дн. — {v['vaccine_name']}"
                    else:
                        next_vaccine_str = f"{v['scheduled_date']} — {v['vaccine_name']}"
                    break
            except Exception:
                continue

    # ── Следующий плановый осмотр ──────────────────────────────────────
    try:
        from handlers.checkups import get_checkup_dates
        checkups = get_checkup_dates(ch["birthdate"])
        next_checkup_str = "—"
        for c in checkups:
            if c["status"] in ("today", "soon", "upcoming"):
                if c["status"] == "today":
                    next_checkup_str = f"Сегодня! — {c['name']}"
                elif c["status"] == "soon":
                    next_checkup_str = f"Через {c['days_diff']} дн. — {c['name']}"
                else:
                    next_checkup_str = f"{c['date']} — {c['name']}"
                break
    except Exception:
        next_checkup_str = "—"

    # ── Активные лекарства ─────────────────────────────────────────────
    meds = db.get_medications(child_id, active_only=True)
    if meds:
        med_names = [m["name"] for m in meds[:3]]
        meds_str = ", ".join(med_names)
        if len(meds) > 3:
            meds_str += f" и ещё {len(meds) - 3}"
    else:
        meds_str = "нет"

    # ── Активная болезнь ───────────────────────────────────────────────
    illnesses = db.get_illnesses(child_id, active_only=True, limit=1)
    illness_str = ""
    if illnesses:
        illness_str = f"\n🤒 *Болеет сейчас:* {illnesses[0]['illness_name']}"

    text = (
        f"{emoji} *{ch['name']}*{illness_str}\n\n"
        f"📅 Дата рождения: {ch['birthdate']}\n"
        f"🎂 Возраст: {age}\n"
        f"👤 Пол: {gender_str}\n\n"
        f"📏 *Последний замер:* {growth_str}\n"
        f"💉 *Ближайшая прививка:* {next_vaccine_str}\n"
        f"🏥 *Следующий осмотр:* {next_checkup_str}\n"
        f"💊 *Активные лекарства:* {meds_str}"
    )

    keyboard = [
        [
            InlineKeyboardButton("📏 Рост и вес",   callback_data=f"growth_menu:{child_id}"),
            InlineKeyboardButton("💉 Прививки",      callback_data=f"vaccines_menu:{child_id}"),
        ],
        [
            InlineKeyboardButton("🏥 Осмотры",       callback_data=f"checkup_child:{child_id}"),
            InlineKeyboardButton("💊 Лекарства",     callback_data=f"med_child:{child_id}"),
        ],
        [
            InlineKeyboardButton("📄 PDF",           callback_data=f"pdf_export:{child_id}"),
            InlineKeyboardButton("📊 Excel",         callback_data=f"excel_export:{child_id}"),
        ],
        [InlineKeyboardButton("🗑 Удалить",          callback_data=f"child_delete:{child_id}")],
        [InlineKeyboardButton("◀️ Назад",            callback_data="my_child")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def start_add_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["adding_child"] = {}
    await query.edit_message_text(
        "👶 *Добавление ребёнка*\n\nВведите имя ребёнка:",
        parse_mode="Markdown"
    )
    return CHILD_NAME


async def got_child_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Имя не может быть пустым. Введите имя:")
        return CHILD_NAME
    context.user_data["adding_child"]["name"] = name
    await update.message.reply_text(
        f"Имя: *{name}*\n\nВведите дату рождения в формате ДД.ММ.ГГГГ:",
        parse_mode="Markdown"
    )
    return CHILD_DATE


async def got_child_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        bd = datetime.strptime(text, "%d.%m.%Y")
        if bd.date() > date.today():
            await update.message.reply_text("Дата не может быть в будущем. Попробуйте снова:")
            return CHILD_DATE
    except ValueError:
        await update.message.reply_text(
            "Неверный формат. Введите дату в виде ДД.ММ.ГГГГ (например, 15.03.2023):"
        )
        return CHILD_DATE

    context.user_data["adding_child"]["birthdate"] = text
    keyboard = [[
        InlineKeyboardButton("👦 Мальчик", callback_data="gender_boy"),
        InlineKeyboardButton("👧 Девочка", callback_data="gender_girl"),
    ]]
    await update.message.reply_text(
        "Выберите пол ребёнка:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHILD_GENDER


async def got_child_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    gender = "boy" if query.data == "gender_boy" else "girl"
    data = context.user_data.get("adding_child", {})
    user_id = update.effective_user.id

    child_id = db.add_child(user_id, data["name"], data["birthdate"], gender)
    emoji = "👧" if gender == "girl" else "👦"

    _seed_vaccination_schedule(child_id, user_id, data["birthdate"])

    keyboard = [[InlineKeyboardButton("👶 Мои дети", callback_data="my_child")]]
    await query.edit_message_text(
        f"✅ {emoji} *{data['name']}* добавлен(а)!\n\nКалендарь прививок создан автоматически.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.pop("adding_child", None)
    return ConversationHandler.END


async def confirm_delete_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return
    keyboard = [[
        InlineKeyboardButton("✅ Да, удалить", callback_data=f"child_delete_confirm:{child_id}"),
        InlineKeyboardButton("❌ Отмена",       callback_data=f"child_view:{child_id}")
    ]]
    await query.edit_message_text(
        f"⚠️ Удалить *{ch['name']}* и все его данные (рост, прививки)?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def do_delete_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    db.delete_child(child_id, user_id)
    keyboard = [[InlineKeyboardButton("👶 Мои дети", callback_data="my_child")]]
    await query.edit_message_text("🗑 Ребёнок удалён.", reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("adding_child", None)
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def _seed_vaccination_schedule(child_id: int, user_id: int, birthdate_str: str):
    try:
        bd = datetime.strptime(birthdate_str, "%d.%m.%Y").date()
    except Exception:
        return

    from dateutil.relativedelta import relativedelta
    from datetime import timedelta

    def _d(months=0, days=0):
        if months:
            return (bd + relativedelta(months=months)).strftime("%d.%m.%Y")
        return (bd + timedelta(days=days)).strftime("%d.%m.%Y")

    schedule = [
        ("БЦЖ (туберкулёз)",                                          _d(days=3)),
        ("Гепатит B (1-я доза)",                                       _d(days=1)),
        ("Гепатит B (2-я доза)",                                       _d(months=1)),
        ("Пневмококк (1-я доза)",                                      _d(months=2)),
        ("АКДС (1-я доза) + Полиомиелит + Hib",                       _d(months=3)),
        ("АКДС (2-я доза) + Полиомиелит + Hib",                       _d(months=4)),
        ("Пневмококк (2-я доза) + АКДС (3-я доза) + Полиомиелит + Hib", _d(months=6)),
        ("Гепатит B (3-я доза)",                                       _d(months=6)),
        ("Корь, краснуха, паротит (1-я доза)",                        _d(months=12)),
        ("Ветряная оспа (1-я доза)",                                   _d(months=12)),
        ("Пневмококк (ревакцинация)",                                  _d(months=15)),
        ("АКДС (ревакцинация 1) + Полиомиелит + Hib",                 _d(months=18)),
        ("Полиомиелит (ревакцинация 2)",                               _d(months=20)),
        ("Корь, краснуха, паротит (ревакцинация)",                    _d(months=72)),
    ]

    for vaccine_name, sched_date in schedule:
        db.add_vaccination(user_id, child_id, vaccine_name, scheduled_date=sched_date)
