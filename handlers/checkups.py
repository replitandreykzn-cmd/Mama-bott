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


def get_checkup_dates(birthdate_str: str, done_months: set = None):
    """Возвращает список осмотров с датами и статусами."""
    try:
        bd = datetime.strptime(birthdate_str, "%d.%m.%Y").date()
    except Exception:
        return []

    today = date.today()
    done_months = done_months or set()
    result = []

    for name, months in CHECKUP_SCHEDULE:
        visit_date = bd + relativedelta(months=months)
        days_diff = (visit_date - today).days

        # Если отмечен вручную как пройденный
        if months in done_months:
            status = "done"
        elif days_diff < -30:
            status = "past"
        elif days_diff < 0:
            status = "overdue"
        elif days_diff == 0:
            status = "today"
        elif days_diff <= 14:
            status = "soon"
        else:
            status = "upcoming"

        result.append({
            "name": name,
            "months": months,
            "date": visit_date.strftime("%d.%m.%Y"),
            "days_diff": days_diff,
            "status": status,
        })
    return result


async def show_checkups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    child_id = ch["id"]
    done_months = db.get_checkups_done(child_id)
    checkups = get_checkup_dates(ch["birthdate"], done_months)
    emoji = "👧" if ch["gender"] == "girl" else "👦"
    age = age_str(ch["birthdate"])

    next_visit = None
    for c in checkups:
        if c["status"] in ("soon", "upcoming", "today"):
            next_visit = c
            break

    lines = []
    shown = 0
    for c in checkups:
        if c["status"] in ("past", "done") and c["status"] != "done":
            continue
        if c["status"] == "done":
            icon = "✅"
            diff_str = "пройден"
        elif c["status"] == "overdue":
            icon = "⚠️"
            diff_str = f"просрочен на {abs(c['days_diff'])} дн."
        elif c["status"] == "today":
            icon = "🔴"
            diff_str = "сегодня!"
        elif c["status"] == "soon":
            icon = "🟡"
            diff_str = f"через {c['days_diff']} дн."
        else:
            icon = "⚪"
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
        [InlineKeyboardButton("📋 Все осмотры", callback_data=f"checkup_all:{child_id}")],
        [InlineKeyboardButton("✅ Отметить пройденным", callback_data=f"checkup_mark_list:{child_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="my_child")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def _show_checkups_msg(message, ch):
    child_id = ch["id"]
    done_months = db.get_checkups_done(child_id)
    checkups = get_checkup_dates(ch["birthdate"], done_months)
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

    upcoming = [c for c in checkups if c["status"] not in ("past",)][:6]
    lines = []
    for c in upcoming:
        if c["status"] == "done":
            icon, diff = "✅", "пройден"
        elif c["status"] == "overdue":
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
        [InlineKeyboardButton("✅ Отметить пройденным", callback_data=f"checkup_mark_list:{ch['id']}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="my_child")],
    ]
    await message.reply_text(text, parse_mode="Markdown",
                             reply_markup=InlineKeyboardMarkup(keyboard))


async def show_all_checkups_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return

    done_months = db.get_checkups_done(child_id)
    checkups = get_checkup_dates(ch["birthdate"], done_months)
    emoji = "👧" if ch["gender"] == "girl" else "👦"

    lines = []
    for c in checkups:
        if c["status"] == "done":
            icon = "✅"
        elif c["status"] == "past":
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
    text += "\n\n✅ пройден  ⚠️ просрочен  🟡 скоро  ⚪ предстоит"

    keyboard = [
        [InlineKeyboardButton("✅ Отметить пройденным", callback_data=f"checkup_mark_list:{child_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"checkup_child:{child_id}")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def show_mark_checkup_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список осмотров которые можно отметить пройденными."""
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return

    done_months = db.get_checkups_done(child_id)
    checkups = get_checkup_dates(ch["birthdate"], done_months)

    # Показываем только те что не отмечены как done и не "past"
    markable = [c for c in checkups if c["status"] != "done"]

    if not markable:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"checkup_child:{child_id}")]]
        await query.edit_message_text(
            "✅ Все осмотры уже отмечены как пройденные!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    keyboard = []
    for c in markable:
        if c["status"] == "overdue":
            label = f"⚠️ {c['name']}"
        elif c["status"] == "today":
            label = f"🔴 {c['name']}"
        elif c["status"] == "soon":
            label = f"🟡 {c['name']}"
        elif c["status"] == "past":
            label = f"✓ {c['name']}"
        else:
            label = f"⚪ {c['name']}"
        keyboard.append([InlineKeyboardButton(
            label, callback_data=f"checkup_mark:{child_id}:{c['months']}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"checkup_child:{child_id}")])

    await query.edit_message_text(
        "✅ *Отметить осмотр пройденным*\n\nВыберите осмотр:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def mark_checkup_done_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмечает осмотр как пройденный."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    child_id = int(parts[1])
    months = int(parts[2])
    user_id = update.effective_user.id

    db.mark_checkup_done(child_id, months)

    # Находим название осмотра
    name = next((n for n, m in CHECKUP_SCHEDULE if m == months), f"{months} мес.")

    keyboard = [[InlineKeyboardButton("🏥 К осмотрам", callback_data=f"checkup_child:{child_id}")]]
    await query.edit_message_text(
        f"✅ Осмотр отмечен как пройденный!\n\n*{name}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def send_checkup_reminders(app):
    """Планировщик: уведомляет об осмотрах за 3 дня и в день осмотра."""
    today = date.today()

    users_children = {}
    all_users = db.get_all_users()
    for u in all_users:
        children = db.get_children(u["user_id"])
        if children:
            users_children[u["user_id"]] = children

    for user_id, children in users_children.items():
        for ch in children:
            done_months = db.get_checkups_done(ch["id"])
            checkups = get_checkup_dates(ch["birthdate"], done_months)
            emoji = "👧" if ch["gender"] == "girl" else "👦"
            for c in checkups:
                if c["status"] == "done":
                    continue
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
