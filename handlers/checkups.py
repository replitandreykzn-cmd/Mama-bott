"""
Плановые осмотры педиатра по возрасту ребёнка (приказ МЗ РФ №514н).
"""
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from handlers.child import age_str

# Плановые осмотры: (название, возраст в месяцах)
CHECKUP_SCHEDULE = [
    ("Новорождённый (педиатр)", 0),
    ("1 месяц", 1),
    ("2 месяца", 2),
    ("3 месяца", 3),
    ("4 месяца", 4),
    ("5 месяцев", 5),
    ("6 месяцев", 6),
    ("7 месяцев", 7),
    ("8 месяцев", 8),
    ("9 месяцев", 9),
    ("10 месяцев", 10),
    ("11 месяцев", 11),
    ("12 месяцев (1 год)", 12),
    ("18 месяцев", 18),
    ("2 года", 24),
    ("3 года", 36),
    ("4 года", 48),
    ("5 лет", 60),
    ("6 лет", 72),
    ("7 лет", 84),
]


def get_checkup_dates(birthdate_str: str):
    """Возвращает список осмотров с датами и статусами."""
    try:
        bd = datetime.strptime(birthdate_str, "%d.%m.%Y").date()
    except Exception:
        return []

    today = date.today()
    result = []
    for name, months in CHECKUP_SCHEDULE:
        visit_date = bd + relativedelta(months=months)
        days_diff = (visit_date - today).days
        if days_diff < -30:
            status = "past"       # давно прошёл
        elif days_diff < 0:
            status = "overdue"    # просрочен (до 30 дней назад)
        elif days_diff == 0:
            status = "today"
        elif days_diff <= 14:
            status = "soon"       # скоро (в ближайшие 2 недели)
        else:
            status = "upcoming"   # предстоит

        result.append({
            "name": name,
            "date": visit_date.strftime("%d.%m.%Y"),
            "days_diff": days_diff,
            "status": status,
        })
    return result


async def show_checkups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора ребёнка для осмотров."""
    query = update.callback_query
    user_id = update.effective_user.id
    children = db.get_children(user_id)

    is_cb = query is not None
    if is_cb:
        await query.answer()

    if not children:
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child")]]
        text = "🏥 *Плановые осмотры*\n\nСначала добавьте ребёнка."
        if is_cb:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if len(children) == 1:
        # Сразу показываем осмотры для единственного ребёнка
        context.user_data["checkup_child_id"] = children[0]["id"]
        if is_cb:
            await _show_checkups_for_child(query, children[0])
        else:
            await _show_checkups_msg(update.message, children[0])
        return

    keyboard = []
    for ch in children:
        emoji = "👧" if ch["gender"] == "girl" else "👦"
        age = age_str(ch["birthdate"])
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {ch['name']} · {age}",
            callback_data=f"checkup_child:{ch['id']}"
        )])

    text = "🏥 *Плановые осмотры педиатра*\n\nВыберите ребёнка:"
    markup = InlineKeyboardMarkup(keyboard)
    if is_cb:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def show_checkups_for_child_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return
    await _show_checkups_for_child(query, ch)


async def _show_checkups_for_child(query, ch):
    checkups = get_checkup_dates(ch["birthdate"])
    emoji = "👧" if ch["gender"] == "girl" else "👦"
    age = age_str(ch["birthdate"])

    # Находим следующий предстоящий осмотр
    next_visit = None
    for c in checkups:
        if c["status"] in ("soon", "upcoming", "today"):
            next_visit = c
            break

    lines = []
    shown = 0
    for c in checkups:
        if c["status"] == "past":
            continue  # скрываем давно прошедшие
        if c["status"] == "past":
            icon = "✓"
        elif c["status"] == "overdue":
            icon = "⚠️"
        elif c["status"] == "today":
            icon = "🔴"
        elif c["status"] == "soon":
            icon = "🟡"
        else:
            icon = "⚪"

        if c["status"] == "overdue":
            diff_str = f"просрочен на {abs(c['days_diff'])} дн."
        elif c["status"] == "today":
            diff_str = "сегодня!"
        elif c["status"] == "soon":
            diff_str = f"через {c['days_diff']} дн."
        else:
            diff_str = c["date"]

        lines.append(f"{icon} {c['name']} — {diff_str}")
        shown += 1
        if shown >= 8:
            break

    text = f"🏥 *Плановые осмотры*\n{emoji} {ch['name']} · {age}\n\n"

    if next_visit:
        if next_visit["status"] == "today":
            text += f"📍 *Сегодня осмотр:* {next_visit['name']}\n\n"
        elif next_visit["status"] == "soon":
            text += f"📍 *Следующий осмотр:* {next_visit['name']}\n"
            text += f"    📅 {next_visit['date']} (через {next_visit['days_diff']} дн.)\n\n"
        else:
            text += f"📍 *Следующий осмотр:* {next_visit['name']}\n"
            text += f"    📅 {next_visit['date']}\n\n"

    if lines:
        text += "*Ближайшие осмотры:*\n" + "\n".join(lines)
    else:
        text += "_Все плановые осмотры пройдены!_ ✅"

    keyboard = [
        [InlineKeyboardButton("📋 Все осмотры", callback_data=f"checkup_all:{ch['id']}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="my_child")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_checkups_msg(message, ch):
    checkups = get_checkup_dates(ch["birthdate"])
    emoji = "👧" if ch["gender"] == "girl" else "👦"
    age = age_str(ch["birthdate"])

    next_visit = None
    for c in checkups:
        if c["status"] in ("soon", "upcoming", "today"):
            next_visit = c
            break

    text = f"🏥 *Плановые осмотры*\n{emoji} {ch['name']} · {age}\n\n"

    if next_visit:
        if next_visit["status"] == "today":
            text += f"📍 *Сегодня осмотр:* {next_visit['name']}\n\n"
        elif next_visit["status"] == "soon":
            text += f"📍 *Следующий осмотр:* {next_visit['name']}\n"
            text += f"    📅 {next_visit['date']} (через {next_visit['days_diff']} дн.)\n\n"
        else:
            text += f"📍 *Следующий осмотр:* {next_visit['name']}\n"
            text += f"    📅 {next_visit['date']}\n\n"

    upcoming = [c for c in checkups if c["status"] != "past"][:6]
    lines = []
    for c in upcoming:
        if c["status"] == "overdue":
            icon, diff = "⚠️", f"просрочен на {abs(c['days_diff'])} дн."
        elif c["status"] == "today":
            icon, diff = "🔴", "сегодня!"
        elif c["status"] == "soon":
            icon, diff = "🟡", f"через {c['days_diff']} дн."
        else:
            icon, diff = "⚪", c["date"]
        lines.append(f"{icon} {c['name']} — {diff}")

    if lines:
        text += "*Ближайшие осмотры:*\n" + "\n".join(lines)

    keyboard = [
        [InlineKeyboardButton("📋 Все осмотры", callback_data=f"checkup_all:{ch['id']}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="my_child")],
    ]
    await message.reply_text(text, parse_mode="Markdown",
                             reply_markup=InlineKeyboardMarkup(keyboard))


async def show_all_checkups_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает полный список всех осмотров."""
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return

    checkups = get_checkup_dates(ch["birthdate"])
    emoji = "👧" if ch["gender"] == "girl" else "👦"

    lines = []
    for c in checkups:
        if c["status"] == "past":
            icon = "✓"
        elif c["status"] == "overdue":
            icon = "⚠️"
        elif c["status"] == "today":
            icon = "🔴"
        elif c["status"] == "soon":
            icon = "🟡"
        else:
            icon = "⚪"
        lines.append(f"{icon} {c['name']} — {c['date']}")

    text = f"📋 *Все плановые осмотры*\n{emoji} {ch['name']}\n\n" + "\n".join(lines)
    text += "\n\n✓ пройден  ⚠️ просрочен  🟡 скоро  ⚪ предстоит"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"checkup_child:{child_id}")]]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def send_checkup_reminders(app):
    """Планировщик: уведомляет о осмотрах за 3 дня и в день осмотра."""
    from datetime import date
    today = date.today()

    users_children = {}
    all_users = db.get_all_users()
    for u in all_users:
        children = db.get_children(u["user_id"])
        if children:
            users_children[u["user_id"]] = children

    for user_id, children in users_children.items():
        for ch in children:
            checkups = get_checkup_dates(ch["birthdate"])
            emoji = "👧" if ch["gender"] == "girl" else "👦"
            for c in checkups:
                if c["status"] == "today":
                    family_ids = db.get_family_user_ids(user_id)
                    for uid in family_ids:
                        try:
                            await app.bot.send_message(
                                chat_id=uid,
                                text=(
                                    f"🏥 *Сегодня плановый осмотр!*\n\n"
                                    f"{emoji} {ch['name']} — *{c['name']}*\n\n"
                                    f"Не забудьте взять полис и карту ребёнка!"
                                ),
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                elif c["days_diff"] == 3:
                    family_ids = db.get_family_user_ids(user_id)
                    for uid in family_ids:
                        try:
                            await app.bot.send_message(
                                chat_id=uid,
                                text=(
                                    f"🏥 *Через 3 дня плановый осмотр*\n\n"
                                    f"{emoji} {ch['name']} — *{c['name']}*\n"
                                    f"📅 {c['date']}\n\n"
                                    f"Запишитесь к педиатру заранее!"
                                ),
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
