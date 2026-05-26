import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from datetime import datetime, timedelta
import database as db

OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "")
PREMIUM_PRICE = os.environ.get("PREMIUM_PRICE", "300 ₽/мес")
TRIAL_DAYS = 14

FAMILY_ADD_ID = range(30, 31)


async def show_subscription_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    premium = db.is_premium(user_id)
    user = db.get_user(user_id)

    if premium:
        until = user["premium_until"] if user else None
        until_str = "—"
        if until:
            try:
                until_str = datetime.fromisoformat(until).strftime("%d.%m.%Y")
            except Exception:
                until_str = until

        members = db.get_family_members(user_id)
        family_info = ""
        if members:
            names = [m["first_name"] or m["username"] or str(m["member_user_id"]) for m in members]
            family_info = f"\n👨‍👩‍👧 *Семейный доступ:* {', '.join(names)}"

        text = (
            "⭐ *Premium активен*\n\n"
            f"📅 Действует до: {until_str}"
            f"{family_info}\n\n"
            "✅ *Ваши возможности:*\n"
            "• Неограниченное количество детей\n"
            "• Полная история роста и веса\n"
            "• Все прививки и напоминания\n"
            "• PDF-экспорт карты ребёнка\n"
            "• Семейный доступ (до 5 чел.)\n"
            "• Еженедельные напоминания о прививках"
        )
        keyboard = [
            [InlineKeyboardButton("👨‍👩‍👧 Управление семьёй", callback_data="family_menu")],
            [InlineKeyboardButton("🎁 Пригласить подругу", callback_data="referral")],
        ]
    else:
        trial_used = user["trial_used"] if user else False
        trial_btn = (
            [InlineKeyboardButton(f"🎁 Бесплатный период ({TRIAL_DAYS} дней)", callback_data="sub_trial")]
            if not trial_used else []
        )
        text = (
            "⭐ *Premium подписка*\n\n"
            "🆓 *Бесплатно:*\n"
            "• 1 ребёнок\n"
            "• Базовый календарь прививок\n"
            "• История роста (последние 5 записей)\n\n"
            f"⭐ *Premium — {PREMIUM_PRICE}:*\n"
            "• Неограниченное количество детей\n"
            "• Полная история роста и веса\n"
            "• Все прививки и напоминания\n"
            "• PDF-экспорт карты ребёнка\n"
            "• Семейный доступ (до 5 чел.)\n"
            "• Лекарства, журнал болезней\n"
            "• Еженедельные напоминания о прививках\n\n"
            "💳 Для оплаты нажмите кнопку ниже:"
        )
        keyboard = (
            trial_btn
            + [
                [InlineKeyboardButton("💳 Купить Premium", callback_data="sub_buy")],
                [InlineKeyboardButton("🎁 Пригласить подругу (+7 дней)", callback_data="referral")],
                [InlineKeyboardButton("💬 Написать администратору", url=f"https://t.me/{OWNER_USERNAME}")],
            ]
        )

    markup = InlineKeyboardMarkup(keyboard)
    if query:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def activate_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    until = db.activate_trial(user_id)
    if until is None:
        keyboard = [[InlineKeyboardButton("⭐ Подписка", callback_data="subscription")]]
        await query.edit_message_text(
            "ℹ️ Вы уже использовали бесплатный период.\n\nДля продления — купите Premium.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    until_str = datetime.fromisoformat(until).strftime("%d.%m.%Y")
    await query.edit_message_text(
        f"🎉 *Premium активирован!*\n\n"
        f"Бесплатный период {TRIAL_DAYS} дней — до {until_str}.\n\n"
        f"Все функции доступны без ограничений!",
        parse_mode="Markdown"
    )


async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("💬 Написать администратору", url=f"https://t.me/{OWNER_USERNAME}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="subscription")],
    ]
    await query.edit_message_text(
        f"💳 *Покупка Premium*\n\n"
        f"Стоимость: *{PREMIUM_PRICE}*\n"
        f"Оплата: карта РФ, СБП, Сбер\n\n"
        f"Нажмите кнопку ниже чтобы написать администратору.\n\n"
        f"В сообщении укажите ваш Telegram ID:\n`{query.from_user.id}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )


# ── Семейный доступ ──────────────────────────────────────────────────────────

async def show_family_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not db.is_premium(user_id):
        keyboard = [[InlineKeyboardButton("⭐ Подписка", callback_data="subscription")]]
        await query.edit_message_text(
            "👨‍👩‍👧 Семейный доступ доступен только для Premium-пользователей.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    members = db.get_family_members(user_id)
    lines = []
    for m in members:
        name = m["first_name"] or m["username"] or str(m["member_user_id"])
        lines.append(f"• {name} (ID: {m['member_user_id']})")

    text = "👨‍👩‍👧 *Семейный доступ*\n\n"
    if lines:
        text += "Участники:\n" + "\n".join(lines) + "\n\n"
    else:
        text += "_Участников пока нет_\n\n"
    text += (
        "Участники видят всех детей и могут добавлять записи роста, "
        "отмечать прививки и создавать напоминания.\n\n"
        "Максимум: 5 участников."
    )

    keyboard = []
    if len(members) < 5:
        keyboard.append([InlineKeyboardButton("➕ Добавить участника", callback_data="family_add")])
    for m in members:
        name = m["first_name"] or m["username"] or str(m["member_user_id"])
        keyboard.append([InlineKeyboardButton(
            f"🗑 Убрать {name}", callback_data=f"family_remove:{m['member_user_id']}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="subscription")])

    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def start_add_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "👨‍👩‍👧 *Добавить участника семьи*\n\n"
        "Введите Telegram ID человека, которому хотите дать доступ.\n\n"
        "Узнать свой ID можно у бота @userinfobot\n\n"
        "Введите числовой ID:",
        parse_mode="Markdown"
    )
    return FAMILY_ADD_ID


async def got_family_member_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        member_id = int(text)
    except ValueError:
        await update.message.reply_text("Введите числовой Telegram ID (например: 123456789):")
        return FAMILY_ADD_ID

    user_id = update.effective_user.id
    if member_id == user_id:
        await update.message.reply_text("Нельзя добавить себя. Введите ID другого человека:")
        return FAMILY_ADD_ID

    members = db.get_family_members(user_id)
    if len(members) >= 5:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="family_menu")]]
        await update.message.reply_text(
            "Достигнут лимит (5 участников).",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    added = db.add_family_member(user_id, member_id)
    keyboard = [[InlineKeyboardButton("👨‍👩‍👧 К семье", callback_data="family_menu")]]
    if added:
        await update.message.reply_text(
            f"✅ Участник с ID `{member_id}` добавлен!\n\n"
            f"Теперь он может пользоваться ботом со всеми Premium-функциями.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "ℹ️ Этот пользователь уже добавлен.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    return ConversationHandler.END


async def remove_family_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    member_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    db.remove_family_member(user_id, member_id)
    keyboard = [[InlineKeyboardButton("👨‍👩‍👧 К семье", callback_data="family_menu")]]
    await query.edit_message_text(
        f"🗑 Участник с ID {member_id} удалён из семьи.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END
