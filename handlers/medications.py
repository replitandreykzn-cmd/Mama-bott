from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, date, timedelta
import database as db

MED_CHILD, MED_NAME, MED_DOSE, MED_INTERVAL, MED_ENDDATE = range(50, 55)


async def show_medications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    children = db.get_children(user_id)

    if not children:
        text = "💊 *Лекарства*\n\nСначала добавьте ребёнка."
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child")]]
        if query:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if len(children) == 1:
        await _show_meds_for_child(update, context, children[0]["id"], query)
    else:
        keyboard = []
        for ch in children:
            emoji = "👧" if ch["gender"] == "girl" else "👦"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {ch['name']}", callback_data=f"med_child:{ch['id']}"
            )])
        text = "💊 *Лекарства*\n\nВыберите ребёнка:"
        if query:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))


async def show_meds_child_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    await _show_meds_for_child(update, context, child_id, query)


async def _show_meds_for_child(update, context, child_id, query=None):
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    meds = db.get_medications(child_id, active_only=True)
    emoji = "👧" if ch["gender"] == "girl" else "👦"

    lines = []
    for m in meds:
        interval = m["interval_hours"]
        hours = int(interval)
        mins = int((interval - hours) * 60)
        interval_str = f"каждые {hours} ч." if mins == 0 else f"каждые {hours} ч. {mins} мин."
        dose_str = f" · {m['dose']}" if m["dose"] else ""
        try:
            next_at = datetime.fromisoformat(m["next_reminder_at"]).strftime("%H:%M")
        except Exception:
            next_at = "—"
        lines.append(f"💊 *{m['name']}*{dose_str}\n    ⏰ {interval_str} · следующий приём: {next_at}")

    text = f"💊 *Лекарства — {emoji} {ch['name']}*\n\n"
    text += ("\n\n".join(lines)) if lines else "_Активных лекарств нет_"

    keyboard = [
        [InlineKeyboardButton("➕ Добавить лекарство", callback_data=f"med_add:{child_id}")],
    ]
    if meds:
        keyboard.append([InlineKeyboardButton("🗑 Отменить приём", callback_data=f"med_stop_list:{child_id}")])

    if query:
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(keyboard))


async def start_add_medication(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["med_data"] = {"child_id": child_id}
    await query.edit_message_text(
        "💊 *Новое лекарство*\n\nВведите название лекарства\n(например: Нурофен, Амоксициллин, Витамин D):",
        parse_mode="Markdown"
    )
    return MED_NAME


async def got_med_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Введите название лекарства:")
        return MED_NAME
    context.user_data["med_data"]["name"] = name
    await update.message.reply_text(
        f"Лекарство: *{name}*\n\n"
        "💉 Введите дозировку (например: 5 мл, 1 таблетка, 400 мг)\n"
        "Или напишите «-» чтобы пропустить:",
        parse_mode="Markdown"
    )
    return MED_DOSE


async def got_med_dose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["med_data"]["dose"] = None if text == "-" else text
    await update.message.reply_text(
        "⏰ Как часто давать лекарство?\n\n"
        "Введите интервал в часах:\n"
        "• 6 — каждые 6 часов\n"
        "• 8 — каждые 8 часов\n"
        "• 12 — каждые 12 часов\n"
        "• 24 — раз в сутки\n"
        "• 0.5 — каждые 30 минут"
    )
    return MED_INTERVAL


async def got_med_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        hours = float(text)
        if hours <= 0 or hours > 168:
            raise ValueError
        context.user_data["med_data"]["interval_hours"] = hours
    except ValueError:
        await update.message.reply_text("Введите число часов (например: 6, 8, 12 или 24):")
        return MED_INTERVAL

    await update.message.reply_text(
        "📅 До какой даты давать лекарство? (ДД.ММ.ГГГГ)\n"
        "Или напишите «-» если без ограничения по дате:"
    )
    return MED_ENDDATE


async def got_med_enddate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    end_date = None
    if text != "-":
        try:
            datetime.strptime(text, "%d.%m.%Y")
            end_date = text
        except ValueError:
            await update.message.reply_text("Неверный формат. Введите ДД.ММ.ГГГГ или «-»:")
            return MED_ENDDATE

    data = context.user_data.get("med_data", {})
    user_id = update.effective_user.id
    child_id = data["child_id"]
    interval = data["interval_hours"]

    db.add_medication(
        user_id=user_id,
        child_id=child_id,
        name=data["name"],
        dose=data.get("dose"),
        interval_hours=interval,
        end_date=end_date
    )

    hours = int(interval)
    mins = int((interval - hours) * 60)
    interval_str = f"каждые {hours} ч." if mins == 0 else f"каждые {hours} ч. {mins} мин."
    next_time = (datetime.now() + timedelta(hours=interval)).strftime("%H:%M")

    keyboard = [[InlineKeyboardButton("💊 К лекарствам", callback_data=f"med_child:{child_id}")]]
    await update.message.reply_text(
        f"✅ Лекарство добавлено!\n\n"
        f"💊 {data['name']}" + (f" · {data['dose']}" if data.get('dose') else "") + "\n"
        f"⏰ {interval_str}\n"
        f"📍 Следующее напоминание: {next_time}" +
        (f"\n📅 До: {end_date}" if end_date else ""),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.pop("med_data", None)
    return ConversationHandler.END


async def show_stop_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    meds = db.get_medications(child_id, active_only=True)

    if not meds:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"med_child:{child_id}")]]
        await query.edit_message_text("Нет активных лекарств.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for m in meds:
        dose_str = f" · {m['dose']}" if m["dose"] else ""
        keyboard.append([InlineKeyboardButton(
            f"🗑 {m['name']}{dose_str}", callback_data=f"med_stop:{m['id']}:{child_id}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"med_child:{child_id}")])

    await query.edit_message_text(
        "🗑 *Выберите лекарство для отмены:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stop_medication(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    med_id = int(parts[1])
    child_id = int(parts[2])
    user_id = update.effective_user.id
    db.deactivate_medication(med_id, user_id)
    keyboard = [[InlineKeyboardButton("💊 К лекарствам", callback_data=f"med_child:{child_id}")]]
    await query.edit_message_text("✅ Приём лекарства остановлен.", reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel_med(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("med_data", None)
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END
