from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import date, datetime
import database as db

GROWTH_HEIGHT, GROWTH_WEIGHT, GROWTH_DATE = range(10, 13)


async def show_growth_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: int = None):
    query = update.callback_query
    if query:
        await query.answer()
        if child_id is None and ":" in query.data:
            child_id = int(query.data.split(":")[1])

    user_id = update.effective_user.id
    children = db.get_children(user_id)

    if not children:
        text = "📏 *Рост и вес*\n\nСначала добавьте ребёнка в разделе «Мой ребёнок»."
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
                    f"{emoji} {ch['name']}", callback_data=f"growth_menu:{ch['id']}"
                )])
            text = "📏 *Рост и вес*\n\nВыберите ребёнка:"
            if query:
                await query.edit_message_text(text, parse_mode="Markdown",
                                              reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(text, parse_mode="Markdown",
                                                reply_markup=InlineKeyboardMarkup(keyboard))
            return

    context.user_data["growth_child_id"] = child_id
    ch = db.get_child(child_id, user_id)
    records = db.get_growth_records(child_id, user_id, limit=10)

    lines = []
    for r in records:
        parts = [f"📅 {r['date']}"]
        if r["height_cm"]:
            parts.append(f"📏 {r['height_cm']} см")
        if r["weight_kg"]:
            parts.append(f"⚖️ {r['weight_kg']} кг")
        lines.append(" · ".join(parts))

    history = "\n".join(lines) if lines else "_История пуста_"
    emoji = "👧" if ch["gender"] == "girl" else "👦"
    text = f"📏 *Рост и вес — {emoji} {ch['name']}*\n\n{history}"

    keyboard = [
        [InlineKeyboardButton("➕ Добавить запись", callback_data=f"growth_add:{child_id}")],
        [InlineKeyboardButton("◀️ Назад к ребёнку", callback_data=f"child_view:{child_id}")],
    ]

    if query:
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(keyboard))


async def start_add_growth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["growth_child_id"] = child_id
    context.user_data["growth_data"] = {}
    await query.edit_message_text(
        "📏 *Новая запись*\n\nВведите рост в сантиметрах (например: 68.5)\nИли напишите «-» чтобы пропустить:",
        parse_mode="Markdown"
    )
    return GROWTH_HEIGHT


async def got_growth_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "-":
        try:
            val = float(text.replace(",", "."))
            if val < 20 or val > 250:
                raise ValueError
            context.user_data["growth_data"]["height"] = val
        except ValueError:
            await update.message.reply_text("Введите корректный рост (например: 68.5) или «-»:")
            return GROWTH_HEIGHT
    else:
        context.user_data["growth_data"]["height"] = None

    await update.message.reply_text(
        "⚖️ Введите вес в килограммах (например: 7.2)\nИли напишите «-» чтобы пропустить:"
    )
    return GROWTH_WEIGHT


async def got_growth_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text != "-":
        try:
            val = float(text.replace(",", "."))
            if val < 0.5 or val > 300:
                raise ValueError
            context.user_data["growth_data"]["weight"] = val
        except ValueError:
            await update.message.reply_text("Введите корректный вес (например: 7.2) или «-»:")
            return GROWTH_WEIGHT
    else:
        context.user_data["growth_data"]["weight"] = None

    today = date.today().strftime("%d.%m.%Y")
    await update.message.reply_text(
        f"📅 Введите дату измерения (ДД.ММ.ГГГГ)\nИли напишите «+» для сегодня ({today}):"
    )
    return GROWTH_DATE


async def got_growth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "+":
        rec_date = date.today().strftime("%d.%m.%Y")
    else:
        try:
            datetime.strptime(text, "%d.%m.%Y")
            rec_date = text
        except ValueError:
            await update.message.reply_text("Неверный формат. Введите ДД.ММ.ГГГГ или «+» для сегодня:")
            return GROWTH_DATE

    data = context.user_data.get("growth_data", {})
    child_id = context.user_data.get("growth_child_id")
    user_id = update.effective_user.id

    db.add_growth_record(user_id, child_id, rec_date, data.get("height"), data.get("weight"))

    parts = []
    if data.get("height"):
        parts.append(f"📏 {data['height']} см")
    if data.get("weight"):
        parts.append(f"⚖️ {data['weight']} кг")

    keyboard = [[InlineKeyboardButton("📏 К записям", callback_data=f"growth_menu:{child_id}")]]
    await update.message.reply_text(
        f"✅ Запись сохранена!\n{', '.join(parts)}\n📅 {rec_date}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.pop("growth_data", None)
    return ConversationHandler.END


async def cancel_growth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("growth_data", None)
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END
