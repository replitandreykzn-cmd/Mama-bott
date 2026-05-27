import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, date
import database as db

logger = logging.getLogger(__name__)

OWNER_ID = int(os.environ.get("OWNER_TG_ID", "0"))


def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("⛔ Нет доступа.")
            return
        return await func(update, context)
    return wrapper


@owner_only
async def cmd_grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Использование: /grant USER_ID [дней]\n"
            "Пример: `/grant 123456789 30`"
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")
        return

    days = 30
    if len(args) > 1:
        try:
            days = int(args[1])
        except ValueError:
            await update.message.reply_text("❌ Количество дней должно быть числом.")
            return

    from datetime import timedelta
    until = (datetime.now() + timedelta(days=days)).isoformat()
    db.set_premium(target_id, until)
    
    try:
        until_str = datetime.fromisoformat(until).strftime("%d.%m.%Y")
    except Exception:
        until_str = until

    await update.message.reply_text(f"✅ Пользователю `{target_id}` выдан Premium до {until_str}.", parse_mode="Markdown")

    # Уведомляем пользователя
    try:
        await context.application.bot.send_message(
            chat_id=target_id,
            text=f"🎉 Администратор активировал вам *Premium доступ* на {days} дн.!\n📅 Действует до: {until_str}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о выдаче премиума пользователю {target_id}: {e}")


async def check_premium_expiry(app):
    """
    Фоновая задача: проверяет у кого истекает подписка и плавно рассылает уведомления.
    Защищена от лимитов Telegram (Flood Control) и ошибок падения.
    """
    logger.info("Запуск проверки истекающих Premium-подписок...")
    
    try:
        # Получаем всех пользователей с активным премиумом
        rows = db.get_premium_users()
    except Exception as e:
        logger.error(f"Ошибка при получении списка премиум-пользователей из БД: {e}")
        return

    if not rows:
        return

    now = datetime.now()
    today_date = date.today()

    for r in rows:
        if not r.get("premium_until"):
            continue

        try:
            # Парсим дату окончания подписки
            until = datetime.fromisoformat(r["premium_until"])
        except Exception:
            try:
                until = datetime.strptime(r["premium_until"], "%d.%m.%Y")
            except Exception:
                continue

        days_left = (until.date() - today_date).days

        # Напоминание за 3 дня до окончания
        if 3 <= days_left <= 4:
            try:
                keyboard = [[InlineKeyboardButton("💳 Продлить Premium", callback_data="sub_buy")]]
                await app.bot.send_message(
                    chat_id=r["user_id"],
                    text=(
                        f"⚠️ *Ваш Premium заканчивается через {days_left} дня!*\n\n"
                        f"📅 Действует до: {until.strftime('%d.%m.%Y')}\n\n"
                        f"Чтобы не потерять доступ к функциям семейного доступа и трекерам — продлите подписку."
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await asyncio.sleep(0.05)  # Защитная микро-пауза
            except Exception as e:
                logger.warning(f"Не удалось отправить предупреждение об истечении подписки пользователю {r['user_id']}: {e}")

        # Напоминание в последний день
        elif days_left == 0:
            try:
                keyboard = [[InlineKeyboardButton("💳 Продлить Premium", callback_data="sub_buy")]]
                await app.bot.send_message(
                    chat_id=r["user_id"],
                    text=(
                        "⏰ *Ваш Premium заканчивается сегодня!*\n\n"
                        "Продлите подписку, чтобы сохранить автоматические уведомления и доступ для всей семьи."
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                await asyncio.sleep(0.05)  # Защитная микро-пауза
            except Exception as e:
                logger.warning(f"Не удалось отправить финальное уведомление подписки пользователю {r['user_id']}: {e}")
