from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import date, datetime
import database as db

ILL_CHILD, ILL_NAME, ILL_ENTRY_TEMP, ILL_ENTRY_SYM, ILL_ENTRY_MEDS, ILL_ENTRY_NOTES = range(60, 66)


async def show_illness_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    children = db.get_children(user_id)

    if not children:
        text = "🤒 *Журнал болезней*\n\nСначала добавьте ребёнка."
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child")]]
        if query:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if len(children) == 1:
        await _show_illness_for_child(update, context, children[0]["id"], query)
    else:
        keyboard = []
        for ch in children:
            emoji = "👧" if ch["gender"] == "girl" else "👦"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {ch['name']}", callback_data=f"ill_child:{ch['id']}"
            )])
        text = "🤒 *Журнал болезней*\n\nВыберите ребёнка:"
        if query:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))


async def show_illness_child_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    await _show_illness_for_child(update, context, child_id, query)


async def _show_illness_for_child(update, context, child_id, query=None):
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    emoji = "👧" if ch["gender"] == "girl" else "👦"

    active = db.get_illnesses(child_id, active_only=True)
    past = db.get_illnesses(child_id, active_only=False, limit=5)
    past_closed = [i for i in past if not i["is_active"]]

    text = f"🤒 *Журнал болезней — {emoji} {ch['name']}*\n\n"

    keyboard = []

    if active:
        ill = active[0]
        text += f"🔴 *Текущая болезнь:* {ill['illness_name']}\n"
        text += f"📅 Начало: {ill['start_date']}\n\n"

        entries = db.get_illness_entries(ill["id"])
        if entries:
            text += "*Последние записи:*\n"
            for e in entries[-3:]:
                line = f"📅 {e['entry_date']}"
                if e["temperature"]:
                    line += f" · 🌡 {e['temperature']}°"
                if e["symptoms"]:
                    line += f"\n    {e['symptoms'][:60]}"
                text += line + "\n"

        keyboard = [
            [InlineKeyboardButton("➕ Добавить запись", callback_data=f"ill_add_entry:{ill['id']}:{child_id}")],
            [InlineKeyboardButton("✅ Выздоровел", callback_data=f"ill_end:{ill['id']}:{child_id}")],
        ]
        if past_closed:
            keyboard.append([InlineKeyboardButton("📋 История болезней", callback_data=f"ill_history:{child_id}")])
    else:
        if past_closed:
            text += f"Болел(а) {len(past_closed)} раз(а).\n"
        else:
            text += "_Болезней не было_ 🎉\n"
        keyboard = [
            [InlineKeyboardButton("🆕 Заболел(а)", callback_data=f"ill_new:{child_id}")],
        ]
        if past_closed:
            keyboard.append([InlineKeyboardButton("📋 История болезней", callback_data=f"ill_history:{child_id}")])

    if query:
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(keyboard))


async def start_new_illness(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["ill_data"] = {"child_id": child_id}
    await query.edit_message_text(
        "🤒 *Новая болезнь*\n\nКак называется болезнь?\n(например: ОРВИ, ангина, бронхит, отит)\n\n"
        "Или просто напишите «Температура» / «Насморк»:",
        parse_mode="Markdown"
    )
    return ILL_NAME


async def got_illness_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Введите название:")
        return ILL_NAME

    data = context.user_data.get("ill_data", {})
    child_id = data["child_id"]
    user_id = update.effective_user.id
    today = date.today().strftime("%d.%m.%Y")

    ill_id = db.start_illness(user_id, child_id, name, today)

    keyboard = [
        [InlineKeyboardButton("➕ Добавить первую запись", callback_data=f"ill_add_entry:{ill_id}:{child_id}")],
        [InlineKeyboardButton("🤒 К болезни", callback_data=f"ill_child:{child_id}")],
    ]
    await update.message.reply_text(
        f"✅ *{name}* — зафиксировано!\n📅 Начало: {today}\n\nДобавьте первую запись с симптомами и температурой:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.pop("ill_data", None)
    return ConversationHandler.END


async def start_add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    ill_id = int(parts[1])
    child_id = int(parts[2])
    context.user_data["ill_entry"] = {"ill_id": ill_id, "child_id": child_id}
    today = date.today().strftime("%d.%m.%Y")
    await query.edit_message_text(
        f"🌡 *Новая запись*\n\nВведите температуру (например: 38.5)\n"
        f"Или напишите «-» если не измеряли:\n\nДата записи: {today}",
        parse_mode="Markdown"
    )
    return ILL_ENTRY_TEMP


async def got_entry_temp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "-":
        try:
            temp = float(text.replace(",", "."))
            if temp < 35 or temp > 42:
                raise ValueError
            context.user_data["ill_entry"]["temperature"] = temp
        except ValueError:
            await update.message.reply_text("Введите температуру (например: 38.5) или «-»:")
            return ILL_ENTRY_TEMP
    else:
        context.user_data["ill_entry"]["temperature"] = None

    await update.message.reply_text(
        "😷 Опишите симптомы (кашель, насморк, боль в горле...)\n"
        "Или напишите «-» чтобы пропустить:"
    )
    return ILL_ENTRY_SYM


async def got_entry_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["ill_entry"]["symptoms"] = None if text == "-" else text
    await update.message.reply_text(
        "💊 Какие лекарства давали? (Нурофен 5 мл, Називин...)\n"
        "Или напишите «-» чтобы пропустить:"
    )
    return ILL_ENTRY_MEDS


async def got_entry_meds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["ill_entry"]["medications_given"] = None if text == "-" else text
    await update.message.reply_text(
        "📝 Дополнительные заметки (визит к врачу, назначения...)\n"
        "Или напишите «-» чтобы пропустить:"
    )
    return ILL_ENTRY_NOTES


async def got_entry_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    notes = None if text == "-" else text

    entry = context.user_data.get("ill_entry", {})
    ill_id = entry["ill_id"]
    child_id = entry["child_id"]
    today = date.today().strftime("%d.%m.%Y")

    db.add_illness_entry(
        illness_id=ill_id,
        entry_date=today,
        temperature=entry.get("temperature"),
        symptoms=entry.get("symptoms"),
        medications_given=entry.get("medications_given"),
        notes=notes
    )

    parts = []
    if entry.get("temperature"):
        parts.append(f"🌡 {entry['temperature']}°")
    if entry.get("symptoms"):
        parts.append(f"😷 {entry['symptoms']}")
    if entry.get("medications_given"):
        parts.append(f"💊 {entry['medications_given']}")

    keyboard = [
        [InlineKeyboardButton("➕ Ещё запись", callback_data=f"ill_add_entry:{ill_id}:{child_id}")],
        [InlineKeyboardButton("🤒 К болезни", callback_data=f"ill_child:{child_id}")],
    ]
    await update.message.reply_text(
        f"✅ Запись добавлена!\n📅 {today}\n" + "\n".join(parts),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.pop("ill_entry", None)
    return ConversationHandler.END


async def end_illness_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    ill_id = int(parts[1])
    child_id = int(parts[2])
    today = date.today().strftime("%d.%m.%Y")

    ill = db.get_illness(ill_id)
    db.end_illness(ill_id, today)

    # Считаем дни болезни
    try:
        start = datetime.strptime(ill["start_date"], "%d.%m.%Y").date()
        end = date.today()
        days = (end - start).days + 1
        days_str = f" ({days} дн.)"
    except Exception:
        days_str = ""

    keyboard = [[InlineKeyboardButton("🤒 Журнал болезней", callback_data=f"ill_child:{child_id}")]]
    await query.edit_message_text(
        f"✅ *Выздоровление!*\n\n"
        f"🤒 {ill['illness_name']}{days_str}\n"
        f"📅 {ill['start_date']} — {today}\n\n"
        f"Отлично! Скорейшего выздоровления! 🌸",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_illness_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    illnesses = db.get_illnesses(child_id, active_only=False, limit=10)
    emoji = "👧" if ch["gender"] == "girl" else "👦"

    lines = []
    for ill in illnesses:
        icon = "🔴" if ill["is_active"] else "✅"
        end = ill["end_date"] or "сейчас"
        try:
            start = datetime.strptime(ill["start_date"], "%d.%m.%Y").date()
            if ill["end_date"]:
                end_d = datetime.strptime(ill["end_date"], "%d.%m.%Y").date()
                days = (end_d - start).days + 1
                end = f"{ill['end_date']} ({days} дн.)"
        except Exception:
            pass
        lines.append(f"{icon} *{ill['illness_name']}*\n    📅 {ill['start_date']} — {end}")

    text = f"📋 *История болезней — {emoji} {ch['name']}*\n\n"
    text += ("\n\n".join(lines)) if lines else "_Нет записей_"

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"ill_child:{child_id}")]]
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel_illness(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("ill_data", None)
    context.user_data.pop("ill_entry", None)
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END
