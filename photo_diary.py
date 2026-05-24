from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import date
import database as db

PHOTO_WAIT, PHOTO_CHILD, PHOTO_CAPTION = range(40, 43)


async def show_photo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    children = db.get_children(user_id)

    if not children:
        text = "📷 *Фотодневник*\n\nСначала добавьте ребёнка."
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child")]]
        if query:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if len(children) == 1:
        context.user_data["photo_child_id"] = children[0]["id"]
        await _show_child_photos(update, context, children[0]["id"], query)
    else:
        keyboard = []
        for ch in children:
            emoji = "👧" if ch["gender"] == "girl" else "👦"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {ch['name']}", callback_data=f"photo_child_view:{ch['id']}"
            )])
        text = "📷 *Фотодневник*\n\nВыберите ребёнка:"
        if query:
            await query.edit_message_text(text, parse_mode="Markdown",
                                          reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(keyboard))


async def show_child_photos_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["photo_child_id"] = child_id
    await _show_child_photos(update, context, child_id, query)


async def _show_child_photos(update, context, child_id, query=None):
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    photos = db.get_photos(child_id, limit=20)
    emoji = "👧" if ch["gender"] == "girl" else "👦"

    lines = []
    for p in photos[:5]:
        cap = p["caption"] or "без подписи"
        lines.append(f"📅 {p['photo_date']} — {cap[:30]}")

    total = len(photos)
    text = f"📷 *Фотодневник — {emoji} {ch['name']}*\n\n"
    if lines:
        text += f"Последние фото ({total}):\n" + "\n".join(lines)
    else:
        text += "_Фотографий пока нет_"

    keyboard = [
        [InlineKeyboardButton("📤 Добавить фото", callback_data="photo_add")],
    ]
    if photos:
        keyboard.append([InlineKeyboardButton("🖼 Посмотреть фото", callback_data=f"photo_view_list:{child_id}")])

    if query:
        await query.edit_message_text(text, parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(keyboard))


async def start_add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    children = db.get_children(user_id)

    if not children:
        await query.edit_message_text("Сначала добавьте ребёнка.")
        return ConversationHandler.END

    if len(children) == 1:
        context.user_data["photo_child_id"] = children[0]["id"]
        await query.edit_message_text(
            "📸 Отправьте фото:",
        )
        return PHOTO_WAIT
    else:
        keyboard = []
        for ch in children:
            emoji = "👧" if ch["gender"] == "girl" else "👦"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {ch['name']}", callback_data=f"photo_sel_child:{ch['id']}"
            )])
        await query.edit_message_text(
            "Выберите ребёнка для фото:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PHOTO_CHILD


async def select_child_for_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["photo_child_id"] = child_id
    await query.edit_message_text("📸 Отправьте фото:")
    return PHOTO_WAIT


async def got_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data["photo_file_id"] = photo.file_id
    await update.message.reply_text(
        "✏️ Добавьте подпись к фото (например: «Первые шаги!»)\n"
        "Или напишите «-» чтобы сохранить без подписи:"
    )
    return PHOTO_CAPTION


async def got_photo_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption_text = update.message.text.strip()
    caption = None if caption_text == "-" else caption_text

    user_id = update.effective_user.id
    child_id = context.user_data.get("photo_child_id")
    file_id = context.user_data.get("photo_file_id")
    today = date.today().strftime("%d.%m.%Y")

    db.add_photo(user_id, child_id, file_id, caption, today)

    keyboard = [[InlineKeyboardButton("📷 К фотодневнику", callback_data=f"photo_child_view:{child_id}")]]
    await update.message.reply_text(
        f"✅ Фото сохранено!\n📅 {today}" + (f"\n✏️ {caption}" if caption else ""),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data.pop("photo_file_id", None)
    return ConversationHandler.END


async def show_photo_view_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    photos = db.get_photos(child_id, limit=10)

    if not photos:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"photo_child_view:{child_id}")]]
        await query.edit_message_text("Фотографий нет.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for p in photos:
        cap = p["caption"] or "без подписи"
        label = f"📅 {p['photo_date']} — {cap[:25]}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"photo_show:{p['id']}:{child_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"photo_child_view:{child_id}")])

    await query.edit_message_text(
        "🖼 *Выберите фото:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_single_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    photo_id = int(parts[1])
    child_id = int(parts[2])
    user_id = update.effective_user.id

    conn = db.get_conn()
    p = conn.execute("SELECT * FROM photo_diary WHERE id=?", (photo_id,)).fetchone()
    conn.close()

    if not p:
        await query.edit_message_text("Фото не найдено.")
        return

    caption = p["caption"] or ""
    keyboard = [
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"photo_delete:{photo_id}:{child_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"photo_view_list:{child_id}")],
    ]
    await query.message.reply_photo(
        photo=p["file_id"],
        caption=f"📅 {p['photo_date']}\n{caption}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await query.edit_message_reply_markup(reply_markup=None)


async def delete_photo_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    photo_id = int(parts[1])
    child_id = int(parts[2])
    user_id = update.effective_user.id
    db.delete_photo(photo_id, user_id)
    keyboard = [[InlineKeyboardButton("📷 К фотодневнику", callback_data=f"photo_child_view:{child_id}")]]
    await query.message.reply_text("🗑 Фото удалено.", reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("photo_file_id", None)
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END
