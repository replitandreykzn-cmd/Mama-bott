"""
Медицинская информация ребёнка:
- Группа крови и резус-фактор
- Данные полиса ОМС и СНИЛС
- Аллергии и противопоказания
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from handlers.child import age_str

# Состояния диалогов
(
    MI_BLOOD_GROUP, MI_BLOOD_RH,
    MI_POLICY_NUMBER, MI_POLICY_COMPANY, MI_SNILS,
    MI_ALLERGY_NAME, MI_ALLERGY_REACTION, MI_ALLERGY_SEVERITY,
    MI_CONTRA_NAME,
) = range(20, 29)


# ── Главное меню медкарты ─────────────────────────────────────────────────────

async def show_medical_info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    children = db.get_children(user_id)
    is_cb = query is not None

    if is_cb:
        await query.answer()

    if not children:
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child")]]
        text = "🏥 *Медкарта*\n\nСначала добавьте ребёнка."
        if is_cb:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if len(children) == 1:
        context.user_data["mi_child_id"] = children[0]["id"]
        await _show_child_medical(query or update, children[0], is_cb)
        return

    keyboard = []
    for ch in children:
        emoji = "👧" if ch["gender"] == "girl" else "👦"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {ch['name']}", callback_data=f"mi_child:{ch['id']}"
        )])

    text = "🏥 *Медкарта*\n\nВыберите ребёнка:"
    markup = InlineKeyboardMarkup(keyboard)
    if is_cb:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def show_medical_info_child_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return
    context.user_data["mi_child_id"] = child_id
    await _show_child_medical(query, ch, is_cb=True)


async def _show_child_medical(query_or_update, ch, is_cb):
    child_id = ch["id"]
    emoji = "👧" if ch["gender"] == "girl" else "👦"
    age = age_str(ch["birthdate"])

    info = db.get_medical_info(child_id)
    allergies = db.get_allergies(child_id)
    contras = db.get_contraindications(child_id)

    # Группа крови
    blood = "—"
    if info and info["blood_group"]:
        rh = info["blood_rh"] or ""
        blood = f"{info['blood_group']} ({rh})" if rh else info["blood_group"]

    # Полис
    policy = "—"
    if info and info["policy_number"]:
        policy = info["policy_number"]
        if info["policy_company"]:
            policy += f"\n    {info['policy_company']}"

    snils = (info["snils"] if info and info["snils"] else "—")

    # Аллергии
    if allergies:
        allergy_lines = []
        for a in allergies:
            sev = {"mild": "🟡 лёгкая", "moderate": "🟠 средняя", "severe": "🔴 тяжёлая"}.get(a["severity"], "")
            line = f"• {a['name']}"
            if a["reaction"]:
                line += f" — {a['reaction']}"
            if sev:
                line += f" ({sev})"
            allergy_lines.append(line)
        allergy_str = "\n".join(allergy_lines)
    else:
        allergy_str = "нет"

    # Противопоказания
    if contras:
        contra_str = "\n".join(f"• {c['name']}" for c in contras)
    else:
        contra_str = "нет"

    text = (
        f"🏥 *Медкарта*\n"
        f"{emoji} {ch['name']} · {age}\n\n"
        f"🩸 *Группа крови:* {blood}\n"
        f"📋 *Полис ОМС:* {policy}\n"
        f"🪪 *СНИЛС:* {snils}\n\n"
        f"⚠️ *Аллергии:*\n{allergy_str}\n\n"
        f"🚫 *Противопоказания:*\n{contra_str}"
    )

    keyboard = [
        [
            InlineKeyboardButton("🩸 Группа крови",    callback_data=f"mi_blood:{child_id}"),
            InlineKeyboardButton("📋 Полис / СНИЛС",   callback_data=f"mi_policy:{child_id}"),
        ],
        [
            InlineKeyboardButton("⚠️ Добавить аллергию",       callback_data=f"mi_allergy_add:{child_id}"),
            InlineKeyboardButton("🚫 Добавить противопок.",     callback_data=f"mi_contra_add:{child_id}"),
        ],
    ]
    if allergies:
        keyboard.append([InlineKeyboardButton("🗑 Удалить аллергию", callback_data=f"mi_allergy_del_list:{child_id}")])
    if contras:
        keyboard.append([InlineKeyboardButton("🗑 Удалить противопок.", callback_data=f"mi_contra_del_list:{child_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="my_child")])

    markup = InlineKeyboardMarkup(keyboard)
    if is_cb:
        await query_or_update.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await query_or_update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


# ── Группа крови ─────────────────────────────────────────────────────────────

async def set_blood_group_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["mi_child_id"] = child_id

    keyboard = [
        [
            InlineKeyboardButton("I (O)",   callback_data="mi_bg:I"),
            InlineKeyboardButton("II (A)",  callback_data="mi_bg:II"),
            InlineKeyboardButton("III (B)", callback_data="mi_bg:III"),
            InlineKeyboardButton("IV (AB)", callback_data="mi_bg:IV"),
        ],
        [InlineKeyboardButton("◀️ Отмена", callback_data=f"mi_child:{child_id}")],
    ]
    await query.edit_message_text(
        "🩸 *Группа крови*\n\nВыберите группу крови:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def got_blood_group_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bg = query.data.split(":")[1]
    context.user_data["mi_blood_group"] = bg

    keyboard = [
        [
            InlineKeyboardButton("+ (положительный)", callback_data="mi_rh:+"),
            InlineKeyboardButton("− (отрицательный)",  callback_data="mi_rh:-"),
        ],
        [InlineKeyboardButton("Не знаю", callback_data="mi_rh:unknown")],
    ]
    await query.edit_message_text(
        f"🩸 Группа крови: *{bg}*\n\nВыберите резус-фактор:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def got_blood_rh_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rh = query.data.split(":")[1]
    if rh == "unknown":
        rh = ""
    child_id = context.user_data.get("mi_child_id")
    bg = context.user_data.get("mi_blood_group", "")
    db.set_medical_info(child_id, blood_group=bg, blood_rh=rh)

    rh_str = f" ({rh})" if rh else ""
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"mi_child:{child_id}")]]
    await query.edit_message_text(
        f"✅ Группа крови сохранена: *{bg}{rh_str}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Полис и СНИЛС ─────────────────────────────────────────────────────────────

async def set_policy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["mi_child_id"] = child_id
    await query.edit_message_text(
        "📋 *Полис ОМС*\n\nВведите номер полиса ОМС:",
        parse_mode="Markdown"
    )
    return MI_POLICY_NUMBER


async def got_policy_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mi_policy_number"] = update.message.text.strip()
    await update.message.reply_text(
        "Введите название страховой компании (или напишите «—» чтобы пропустить):"
    )
    return MI_POLICY_COMPANY


async def got_policy_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    company = update.message.text.strip()
    if company == "—":
        company = ""
    context.user_data["mi_policy_company"] = company
    await update.message.reply_text(
        "Введите СНИЛС (или напишите «—» чтобы пропустить):"
    )
    return MI_SNILS


async def got_snils(update: Update, context: ContextTypes.DEFAULT_TYPE):
    snils = update.message.text.strip()
    if snils == "—":
        snils = ""
    child_id = context.user_data.get("mi_child_id")
    db.set_medical_info(
        child_id,
        policy_number=context.user_data.get("mi_policy_number", ""),
        policy_company=context.user_data.get("mi_policy_company", ""),
        snils=snils
    )
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"mi_child:{child_id}")]]
    await update.message.reply_text(
        "✅ Данные полиса сохранены!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def cancel_mi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    child_id = context.user_data.get("mi_child_id")
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"mi_child:{child_id}" if child_id else "my_child")]]
    await update.message.reply_text("Отменено.", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END


# ── Аллергии ─────────────────────────────────────────────────────────────────

async def start_add_allergy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["mi_child_id"] = child_id
    await query.edit_message_text(
        "⚠️ *Добавить аллергию*\n\nВведите название аллергена\n(например: Пенициллин, Орехи, Кошачья шерсть):",
        parse_mode="Markdown"
    )
    return MI_ALLERGY_NAME


async def got_allergy_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mi_allergy_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Опишите реакцию (сыпь, отёк, анафилаксия и т.д.)\nИли напишите «—» чтобы пропустить:"
    )
    return MI_ALLERGY_REACTION


async def got_allergy_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reaction = update.message.text.strip()
    if reaction == "—":
        reaction = ""
    context.user_data["mi_allergy_reaction"] = reaction

    keyboard = [
        [
            InlineKeyboardButton("🟡 Лёгкая",   callback_data="mi_asev:mild"),
            InlineKeyboardButton("🟠 Средняя",  callback_data="mi_asev:moderate"),
            InlineKeyboardButton("🔴 Тяжёлая",  callback_data="mi_asev:severe"),
        ]
    ]
    await update.message.reply_text(
        "Выберите тяжесть аллергии:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MI_ALLERGY_SEVERITY


async def got_allergy_severity_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    severity = query.data.split(":")[1]
    child_id = context.user_data.get("mi_child_id")

    db.add_allergy(
        child_id,
        name=context.user_data.get("mi_allergy_name", ""),
        reaction=context.user_data.get("mi_allergy_reaction", ""),
        severity=severity
    )
    keyboard = [[InlineKeyboardButton("◀️ К медкарте", callback_data=f"mi_child:{child_id}")]]
    sev_str = {"mild": "🟡 лёгкая", "moderate": "🟠 средняя", "severe": "🔴 тяжёлая"}.get(severity, "")
    await query.edit_message_text(
        f"✅ Аллергия добавлена!\n\n"
        f"*{context.user_data.get('mi_allergy_name')}* — {sev_str}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def show_allergy_delete_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    allergies = db.get_allergies(child_id)
    keyboard = []
    for a in allergies:
        keyboard.append([InlineKeyboardButton(f"🗑 {a['name']}", callback_data=f"mi_allergy_del:{a['id']}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"mi_child:{child_id}")])
    await query.edit_message_text(
        "⚠️ Выберите аллергию для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_allergy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    allergy_id = int(query.data.split(":")[1])
    child_id = db.delete_allergy(allergy_id)
    keyboard = [[InlineKeyboardButton("◀️ К медкарте", callback_data=f"mi_child:{child_id}")]]
    await query.edit_message_text("🗑 Аллергия удалена.", reply_markup=InlineKeyboardMarkup(keyboard))


# ── Противопоказания ──────────────────────────────────────────────────────────

async def start_add_contra_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    context.user_data["mi_child_id"] = child_id
    await query.edit_message_text(
        "🚫 *Добавить противопоказание*\n\nВведите название\n(например: Аспирин, живые вакцины, УФ-облучение):",
        parse_mode="Markdown"
    )
    return MI_CONTRA_NAME


async def got_contra_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    child_id = context.user_data.get("mi_child_id")
    name = update.message.text.strip()
    db.add_contraindication(child_id, name)
    keyboard = [[InlineKeyboardButton("◀️ К медкарте", callback_data=f"mi_child:{child_id}")]]
    await update.message.reply_text(
        f"✅ Противопоказание добавлено: *{name}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def show_contra_delete_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    child_id = int(query.data.split(":")[1])
    contras = db.get_contraindications(child_id)
    keyboard = []
    for c in contras:
        keyboard.append([InlineKeyboardButton(f"🗑 {c['name']}", callback_data=f"mi_contra_del:{c['id']}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"mi_child:{child_id}")])
    await query.edit_message_text(
        "🚫 Выберите противопоказание для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_contra_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    contra_id = int(query.data.split(":")[1])
    child_id = db.delete_contraindication(contra_id)
    keyboard = [[InlineKeyboardButton("◀️ К медкарте", callback_data=f"mi_child:{child_id}")]]
    await query.edit_message_text("🗑 Противопоказание удалено.", reply_markup=InlineKeyboardMarkup(keyboard))
