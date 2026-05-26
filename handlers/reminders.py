from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, date
import database as db

REM_TITLE, REM_DATE, REM_TIME = range(20, 23)


async def show_reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    reminders = db.get_reminders(user_id, active_only=True)

    lines = []
    for r in reminders:
        try:
            dt = datetime.fromisoformat(r["remind_at"])
            dt_str = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            dt_str = r["remind_at"]
        lines.append(f"🔔 {r['title']}\n    📅 {dt_str}")

    text = "🔔 *Напоминания*\n\n"
    text += ("\n\n".join(lines)) if lines else "_Нет активных напоминаний_"

    keyboard = [
        [InlineKeyboardButton("➕ Новое напоминание", callback_data="reminder_add")],
        [InlineKeyboardButton("🗑 Удалить напоминание", callback_data="reminder_delete_list")],
    ]

    if query:
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(keyboard))


async def start_add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["reminder_data"] = {}
    await query.edit_message_text(
        "🔔 *Новое напоминание*\n\nВведите название напоминания\n(например: «Приём у педиатра», «Купить витамин D»):",
        parse_mode="Markdown"
    )
    return REM_TITLE


async def got_reminder_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Название не может быть пустым:")
        return REM_TITLE
    context.user_data["reminder_data"]["title"] = title
    today = date.today().strftime("%d.%m.%Y")
    await update.message.reply_text(
        f"📅 Введите дату напоминания (ДД.ММ.ГГГГ)\nНапример: {today}:"
    )
    return REM_DATE


async def got_reminder_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%d.%m.%Y")
        context.user_data["reminder_data"]["date"] = text
    except ValueError:
        await update.message.reply_text("Неверный формат. Введите ДД.ММ.ГГГГ:")
        return REM_DATE
    await update.message.reply_text(
        "⏰ Введите время напоминания (ЧЧ:ММ)\nНапример: 10:00 или 18:30:"
    )
    return REM_TIME


async def got_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", ":").replace("-", ":")
    # Нормализуем: 8:00 → 08:00, 8.00 → 08:00
    if ":" in text:
        parts = text.split(":")
        text = f"{int(parts[0]):02d}:{parts[1].zfill(2)}"
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await update.message.reply_text("Неверный формат. Введите время (например 9:00 или 09:00):")
        return REM_TIME

    data = context.user_data.get("reminder_data", {})
    date_str = data.get("date")
    remind_at = datetime.strptime(f"{date_str} {text}", "%d.%m.%Y %H:%M").isoformat()

    user_id = update.effective_user.id
    db.add_reminder(user_id, None, data["title"], remind_at)

    keyboard = [[InlineKeyboardButton("🔔 К напоминаниям", callback_data="reminders")]]
    await update.message.reply_text(
        f"✅ Напоминание создано!\n🔔 {data['title']}\n📅 {date_str} в {text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.pop("reminder_data", None)
    return ConversationHandler.END


async def show_delete_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    reminders = db.get_reminders(user_id, active_only=True)

    if not reminders:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="reminders")]]
        await query.edit_message_text("Нет активных напоминаний.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for r in reminders:
        keyboard.append([InlineKeyboardButton(
            f"🗑 {r['title'][:40]}", callback_data=f"reminder_delete:{r['id']}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="reminders")])
    await query.edit_message_text(
        "🗑 *Выберите напоминание для удаления:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def do_delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reminder_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    db.delete_reminder(reminder_id, user_id)
    keyboard = [[InlineKeyboardButton("🔔 К напоминаниям", callback_data="reminders")]]
    await query.edit_message_text("🗑 Напоминание удалено.", reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("reminder_data", None)
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END
