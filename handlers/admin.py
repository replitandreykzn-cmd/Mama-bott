from telegram import Update
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
    """
    /grant USER_ID [DAYS]
    Активирует Premium пользователю на DAYS дней (по умолчанию 30).
    """
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

    # Уведомляем пользователя если он уже в боте
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"🎉 *Ваша Premium-подписка активирована!*\n\n"
                f"📅 Действует до: {until_str}\n\n"
                f"Все функции бота теперь доступны без ограничений!\n"
                f"Используйте /start чтобы начать."
            ),
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text("⚠️ Пользователь ещё не запускал бота — уведомить не удалось.")


@owner_only
async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /revoke USER_ID
    Отзывает Premium у пользователя.
    """
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

    conn = db.get_conn()
    conn.execute("UPDATE users SET is_premium=0, premium_until=NULL WHERE user_id=?", (target_id,))
    conn.commit()
    conn.close()

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
    """
    /stats
    Статистика бота: пользователи, Premium, дети, напоминания.
    """
    conn = db.get_conn()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    premium_users = conn.execute(
        "SELECT COUNT(*) FROM users WHERE is_premium=1 AND (premium_until IS NULL OR premium_until > ?)",
        (datetime.now().isoformat(),)
    ).fetchone()[0]
    trial_users = conn.execute("SELECT COUNT(*) FROM users WHERE trial_used=1").fetchone()[0]
    total_children = conn.execute("SELECT COUNT(*) FROM children").fetchone()[0]
    total_reminders = conn.execute("SELECT COUNT(*) FROM reminders WHERE is_active=1").fetchone()[0]
    total_vaccinations_done = conn.execute("SELECT COUNT(*) FROM vaccinations WHERE done_date IS NOT NULL").fetchone()[0]
    family_links = conn.execute("SELECT COUNT(*) FROM family_members").fetchone()[0]
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
    """
    /broadcast Текст сообщения
    Отправляет сообщение всем пользователям бота.
    """
    if not context.args:
        await update.message.reply_text(
            "Использование: `/broadcast Ваш текст`\nПример: `/broadcast Доброе утро! Новая функция уже в боте.`",
            parse_mode="Markdown"
        )
        return

    text = " ".join(context.args)
    conn = db.get_conn()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()

    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(f"📤 Отправляю {len(users)} пользователям...")

    for row in users:
        try:
            await context.bot.send_message(
                chat_id=row["user_id"],
                text=f"📢 *Сообщение от МамаБота:*\n\n{text}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed} (заблокировали бота)"
    )


@owner_only
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /users
    Список последних 20 пользователей с их Premium-статусом.
    """
    conn = db.get_conn()
    rows = conn.execute(
        """SELECT user_id, username, first_name, is_premium, premium_until, trial_used, created_at
           FROM users ORDER BY created_at DESC LIMIT 20"""
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Пользователей пока нет.")
        return

    now = datetime.now()
    lines = []
    for r in rows:
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
