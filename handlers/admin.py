from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import database as db

OWNER_ID = 6903827237


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
            "Использование: /grant USER\\_ID \\[дней\\]\n"
            "Пример: `/grant 123456789 30`",
            parse_mode="MarkdownV2"
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

    until = (datetime.now() + timedelta(days=days)).isoformat()
    db.set_premium(target_id, until)
    until_str = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")

    await update.message.reply_text(
        f"✅ Premium активирован!\n\n"
        f"👤 ID: `{target_id}`\n"
        f"📅 До: {until_str} ({days} дней)",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"🎉 *Ваша Premium-подписка активирована!*\n\n"
                f"📅 Действует до: {until_str}\n\n"
                f"Все функции бота теперь доступны без ограничений!"
            ),
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text("⚠️ Пользователь ещё не запускал бота — уведомить не удалось.")


@owner_only
async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Использование: `/revoke USER_ID`\nПример: `/revoke 123456789`",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")
        return

    db.revoke_premium(target_id)

    await update.message.reply_text(
        f"✅ Premium отозван у пользователя `{target_id}`.",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="ℹ️ Ваша Premium-подписка завершена. Для продления — напишите владельцу бота.",
        )
    except Exception:
        pass


@owner_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db.get_conn()
    c = conn.cursor()

    def count(sql, params=()):
        c.execute(sql, params)
        row = c.fetchone()
        if isinstance(row, dict):
            return list(row.values())[0]
        return row[0]

    ph = "%s" if db._is_pg() else "?"
    total_users = count("SELECT COUNT(*) FROM users")
    premium_users = count(f"SELECT COUNT(*) FROM users WHERE is_premium=1 AND (premium_until IS NULL OR premium_until > {ph})", (datetime.now().isoformat(),))
    trial_users = count("SELECT COUNT(*) FROM users WHERE trial_used=1")
    total_children = count("SELECT COUNT(*) FROM children")
    total_reminders = count("SELECT COUNT(*) FROM reminders WHERE is_active=1")
    total_vaccinations_done = count("SELECT COUNT(*) FROM vaccinations WHERE done_date IS NOT NULL")
    family_links = count("SELECT COUNT(*) FROM family_members")
    conn.close()

    await update.message.reply_text(
        f"📊 *Статистика МамаБота*\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"⭐ Premium активных: {premium_users}\n"
        f"🎁 Использовали пробный период: {trial_users}\n"
        f"👶 Детей добавлено: {total_children}\n"
        f"🔔 Активных напоминаний: {total_reminders}\n"
        f"💉 Прививок отмечено: {total_vaccinations_done}\n"
        f"👨‍👩‍👧 Семейных связей: {family_links}",
        parse_mode="Markdown"
    )


@owner_only
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Использование: `/broadcast Ваш текст`",
            parse_mode="Markdown"
        )
        return

    text = " ".join(context.args)
    users = db.get_all_users()

    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(f"📤 Отправляю {len(users)} пользователям...")

    for r in users:
        try:
            await context.bot.send_message(
                chat_id=r["user_id"],
                text=f"📢 *Сообщение от МамаБота:*\n\n{text}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}"
    )


@owner_only
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()

    if not users:
        await update.message.reply_text("Пользователей пока нет.")
        return

    now = datetime.now()
    lines = []
    for r in list(users)[:20]:
        name = r["first_name"] or r["username"] or "—"
        premium_icon = "⭐" if r["is_premium"] else "🆓"
        trial_icon = " 🎁" if r["trial_used"] else ""
        until = ""
        if r["premium_until"]:
            try:
                d = datetime.fromisoformat(r["premium_until"])
                if d > now:
                    until = f" до {d.strftime('%d.%m')}"
                else:
                    until = " (истёк)"
            except Exception:
                pass
        lines.append(f"{premium_icon}{trial_icon} {name} | `{r['user_id']}`{until}")

    text = "👥 *Последние пользователи:*\n\n" + "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown")


async def check_premium_expiry(app):
    """Проверяет Premium пользователей и уведомляет об окончании за 3 дня."""
    users = db.get_all_users()
    now = datetime.now()
    warn_date = now + timedelta(days=3)

    for r in users:
        if not r["is_premium"] or not r["premium_until"]:
            continue
        try:
            until = datetime.fromisoformat(r["premium_until"])
        except Exception:
            continue

        # Уведомляем если до конца осталось от 3 до 4 дней
        days_left = (until - now).days
        if 3 <= days_left <= 4:
            try:
                keyboard = [[InlineKeyboardButton(
                    "💳 Продлить Premium", callback_data="sub_buy"
                )]]
                await app.bot.send_message(
                    chat_id=r["user_id"],
                    text=(
                        f"⚠️ *Ваш Premium заканчивается через {days_left} дня!*\n\n"
                        f"📅 Действует до: {until.strftime('%d.%m.%Y')}\n\n"
                        f"Чтобы не потерять доступ к функциям — продлите подписку."
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception:
                pass

        # Уведомляем в день окончания
        elif days_left == 0:
            try:
                keyboard = [[InlineKeyboardButton(
                    "💳 Продлить Premium", callback_data="sub_buy"
                )]]
                await app.bot.send_message(
                    chat_id=r["user_id"],
                    text=(
                        "⏰ *Ваш Premium заканчивается сегодня!*\n\n"
                        "Продлите подписку чтобы сохранить доступ ко всем функциям."
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception:
                pass
