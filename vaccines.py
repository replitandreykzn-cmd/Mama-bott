from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import date, datetime
import database as db


def _status_icon(r) -> str:
    if r["done_date"]:
        return "✅"
    if r["scheduled_date"]:
        try:
            d = datetime.strptime(r["scheduled_date"], "%d.%m.%Y").date()
            if d <= date.today():
                return "⚠️"
        except Exception:
            pass
    return "🔵"


async def show_vaccines_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: int = None):
    query = update.callback_query
    if query:
        await query.answer()
        if child_id is None and ":" in query.data:
            child_id = int(query.data.split(":")[1])

    user_id = update.effective_user.id
    children = db.get_children(user_id)

    if not children:
        text = "💉 *Прививки*\n\nСначала добавьте ребёнка."
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child")]]
        if query:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if child_id is None:
        if len(children) == 1:
            child_id = children[0]["id"]
        else:
            keyboard = []
            for ch in children:
                emoji = "👧" if ch["gender"] == "girl" else "👦"
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {ch['name']}", callback_data=f"vaccines_menu:{ch['id']}"
                )])
            text = "💉 *Прививки*\n\nВыберите ребёнка:"
            if query:
                await query.edit_message_text(text, parse_mode="Markdown",
                                              reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(text, parse_mode="Markdown",
                                                reply_markup=InlineKeyboardMarkup(keyboard))
            return

    context.user_data["vaccines_child_id"] = child_id
    ch = db.get_child(child_id, user_id)
    records = db.get_vaccinations(child_id, user_id)
    emoji = "👧" if ch["gender"] == "girl" else "👦"

    done = [r for r in records if r["done_date"]]
    pending = [r for r in records if not r["done_date"]]
    overdue = [r for r in pending if r["scheduled_date"] and
               datetime.strptime(r["scheduled_date"], "%d.%m.%Y").date() <= date.today()]

    text = f"💉 *Прививки — {emoji} {ch['name']}*\n\n"
    text += f"✅ Сделано: {len(done)}  ⚠️ Просрочено: {len(overdue)}  🔵 Предстоит: {len(pending) - len(overdue)}\n\n"

    if overdue:
        text += "*⚠️ Просроченные:*\n"
        for r in overdue[:3]:
            text += f"  • {r['vaccine_name']} ({r['scheduled_date']})\n"
        text += "\n"

    upcoming = [r for r in pending if r not in overdue][:3]
    if upcoming:
        text += "*🔵 Предстоящие:*\n"
        for r in upcoming:
            text += f"  • {r['vaccine_name']} ({r['scheduled_date']})\n"

    keyboard = [
        [InlineKeyboardButton("📋 Весь список", callback_data=f"vaccines_list:{child_id}")],
        [InlineKeyboardButton("✅ Отметить сделанной", callback_data=f"vaccines_done_list:{child_id}")],
        [InlineKeyboardButton("◀️ Назад к ребёнку", callback_data=f"child_view:{child_id}")],
    ]

    if query:
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(keyboard))


async def show_vaccines_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    records = db.get_vaccinations(child_id, user_id)
    emoji = "👧" if ch["gender"] == "girl" else "👦"

    lines = []
    for r in records:
        icon = _status_icon(r)
        date_str = r["done_date"] if r["done_date"] else r["scheduled_date"] or "—"
        lines.append(f"{icon} {r['vaccine_name']}\n    📅 {date_str}")

    text = (f"💉 *Все прививки — {emoji} {ch['name']}*\n\n" + "\n\n".join(lines)) if lines else "Список пуст."
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"vaccines_menu:{child_id}")]]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def show_done_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    records = db.get_vaccinations(child_id, user_id)
    pending = [r for r in records if not r["done_date"]]

    if not pending:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"vaccines_menu:{child_id}")]]
        await query.edit_message_text("✅ Все прививки уже отмечены как сделанные!",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for r in pending[:10]:
        icon = _status_icon(r)
        label = f"{icon} {r['vaccine_name'][:35]}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"vac_mark:{r['id']}:{child_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"vaccines_menu:{child_id}")])

    await query.edit_message_text(
        "✅ *Выберите прививку для отметки:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def mark_vaccine_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    vac_id = int(parts[1])
    child_id = int(parts[2])
    user_id = update.effective_user.id
    today = date.today().strftime("%d.%m.%Y")
    db.mark_vaccination_done(vac_id, user_id, today)
    keyboard = [[InlineKeyboardButton("💉 К прививкам", callback_data=f"vaccines_menu:{child_id}")]]
    await query.edit_message_text(
        f"✅ Прививка отмечена как сделанная сегодня ({today})!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
