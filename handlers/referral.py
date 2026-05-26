"""
Реферальная система — пригласи подругу, получи +7 дней Premium.
"""
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

BONUS_DAYS = int(os.environ.get("REFERRAL_BONUS_DAYS", "7"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")  # без @


async def show_referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    is_cb = query is not None

    if is_cb:
        await query.answer()

    code = db.get_referral_code(user_id)
    stats = db.get_referral_stats(user_id)

    bot_link = f"https://t.me/{BOT_USERNAME}?start=ref{code}" if BOT_USERNAME else f"Ваш код: ref{code}"

    text = (
        f"🎁 *Реферальная программа*\n\n"
        f"Приглашай подруг — получай Premium!\n\n"
        f"За каждую подругу которая запустит бота по твоей ссылке "
        f"ты получаешь *+{BONUS_DAYS} дней Premium*.\n\n"
        f"📊 *Твоя статистика:*\n"
        f"• Приглашено: {stats['total']} чел.\n"
        f"• Бонусов получено: {stats['bonused']} × {BONUS_DAYS} дн. = {stats['bonused'] * BONUS_DAYS} дн.\n\n"
        f"🔗 *Твоя ссылка:*\n`{bot_link}`\n\n"
        f"_Просто скопируй и отправь подруге!_"
    )

    keyboard = [
        [InlineKeyboardButton("📋 Скопировать ссылку", switch_inline_query=bot_link)],
        [InlineKeyboardButton("◀️ Назад", callback_data="subscription")],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if is_cb:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def handle_referral_start(user_id: int, ref_code: str, app):
    """Вызывается при /start ref<CODE> — начисляет бонус."""
    try:
        referrer_id = int(ref_code.replace("ref", ""))
    except Exception:
        return

    success = db.apply_referral(user_id, referrer_id)
    if not success:
        return

    until = db.give_referral_bonus(referrer_id, BONUS_DAYS)
    if not until:
        return

    from datetime import datetime
    try:
        until_str = datetime.fromisoformat(until).strftime("%d.%m.%Y")
    except Exception:
        until_str = until

    try:
        await app.bot.send_message(
            chat_id=referrer_id,
            text=(
                f"🎉 *По вашей реферальной ссылке зарегистрировалась подруга!*\n\n"
                f"Вам начислено *+{BONUS_DAYS} дней Premium*.\n"
                f"📅 Premium действует до: {until_str}"
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass
