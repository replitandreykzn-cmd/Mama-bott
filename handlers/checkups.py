"""
Плановые осмотры педиатра по возрасту ребёнка (приказ МЗ РФ №514н).
Безопасная рассылка уведомлений с защитой от блокировок Telegram.
"""
import asyncio
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

logger = logging.getLogger(__name__)

# Официальный график осмотров (название, возраст в месяцах)
CHECKUP_SCHEDULE = [
    ("Новорождённый (педиатр)", 0),
    ("1 месяц", 1),
    ("2 месяца", 2),
    ("3 месяца", 3),
    ("4 месяца", 4),
    ("5 месяцев", 5),
    ("6 месяцев", 6),
    ("7 месяцев", 7),
    ("8 месяцев", 8),
    ("9 месяцев", 9),
    ("10 месяцев", 10),
    ("11 месяцев", 11),
    ("12 месяцев (1 год)", 12),
    ("18 месяцев", 18),
    ("2 года", 24),
    ("3 года", 36),
    ("4 года", 48),
    ("5 лет", 60),
    ("6 лет", 72),
    ("7 лет", 84),
]


def age_str_local(birthdate_str: str) -> str:
    """Вспомогательная функция расчета возраста для текста меню."""
    try:
        bd = datetime.strptime(birthdate_str, "%d.%m.%Y").date()
    except Exception:
        return ""
    today = date.today()
    months = (today.year - bd.year) * 12 + today.month - bd.month
    if today.day < bd.day:
        months -= 1
    if months < 0:
        months = 0
    if months < 12:
        return f"{months} мес."
    return f"{months // 12} л. {months % 12} мес."


def get_checkup_dates(birthdate_str: str, done_months: set = None):
    """Возвращает список осмотров с датами и статусами."""
    if done_months is None:
        done_months = set()
    try:
        bd = datetime.strptime(birthdate_str, "%d.%m.%Y").date()
    except Exception:
        return []

    today = date.today()
    results = []

    for name, months in CHECKUP_SCHEDULE:
        checkup_date = bd + relativedelta(months=months)
        is_done = months in done_months
        days_diff = (checkup_date - today).days

        if is_done:
            status = "✅ Пройдено"
        elif 0 <= days_diff <= 7:
            status = "⚠️ Скоро"
        elif days_diff > 7:
            status = "⏳ Ожидается"
        else:
            status = "❌ Пропущено"

        results.append({
            "name": name,
            "months": months,
            "date": checkup_date.strftime("%d.%m.%Y"),
            "status": status,
            "days_diff": days_diff,
            "is_done": is_done
        })
    return results


async def show_checkups_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, child_id: int = None):
    query = update.callback_query
    if query:
        await query.answer()
        if child_id is None and ":" in query.data:
            try:
                child_id = int(query.data.split(":")[1])
            except Exception:
                child_id = None

    user_id = update.effective_user.id
    children = db.get_children(user_id)

    if not children:
        text = "🏥 *Плановые осмотры*\n\nСначала добавьте ребёнка в разделе «Мой ребёнок»."
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child")]]
        if query:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if child_id is None:
        if len(children) == 1:
            child_id = children[0]["id"]
        else:
            keyboard = []
            for ch in children:
                emoji = "👧" if ch["gender"] == "girl" else "👦"
                keyboard.append([InlineKeyboardButton(f"{emoji} {ch['name']}", callback_data=f"checkups_menu:{ch['id']}")])
            text = "🏥 *Плановые осмотры*\n\nВыберите ребёнка для просмотра графика врачей:"
            if query:
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return

    ch = db.get_child(child_id, user_id)
    if not ch:
        if query:
            await query.edit_message_text("❌ Ошибка: Ребёнок не найден.")
        return

    done_months = db.get_checkups_done(child_id)
    schedule = get_checkup_dates(ch["birthdate"], done_months)

    emoji = "👧" if ch["gender"] == "girl" else "👦"
    text = f"🏥 *Осмотры врачей — {emoji} {ch['name']}* ({age_str_local(ch['birthdate'])})\n\n"
    text += "График составлен по приказу Минздрава РФ №514н:\n\n"

    keyboard = []
    visible_count = 0
    for c in schedule:
        if c["is_done"]:
            status_str = "✅"
        elif c["days_diff"] < 0:
            status_str = "🛑"
        elif 0 <= c["days_diff"] <= 14:
            status_str = "🔔"
        else:
            status_str = "⏳"

        if visible_count < 12 or c["days_diff"] >= -30:
            text += f"{status_str} *{c['name']}* — {c['date']}\n"
            if not c["is_done"]:
                keyboard.append([InlineKeyboardButton(f"Отметить пройденным: {c['name']}", callback_data=f"check_done:{c['months']}:{child_id}")])
            visible_count += 1

    keyboard.append([InlineKeyboardButton("◀️ Назад к ребёнку", callback_data=f"child_view:{child_id}")])

    if query:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def mark_checkup_done_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        parts = query.data.split(":")
        months = int(parts[1])
        child_id = int(parts[2])
        db.mark_checkup_done(child_id, months)
        await show_checkups_menu(update, context, child_id=child_id)
    except Exception as e:
        logger.error(f"Ошибка при отметке осмотра: {e}")


async def send_checkup_reminders(app):
    """
    Фоновая задача: проверяет кому пора к врачу и рассылает сообщения.
    Защищена от сбоев и лимитов Telegram (плавная отправка).
    """
    logger.info("Запуск рассылки напоминаний о плановых осмотрах врачей...")
    try:
        children = db.get_all_children_raw()
    except Exception as e:
        logger.error(f"Не удалось получить список детей из БД: {e}")
        return

    if not children:
        return

    for ch in children:
        child_id = ch["id"]
        user_id = ch["user_id"]

        try:
            done_months = db.get_checkups_done(child_id)
            schedule = get_checkup_dates(ch["birthdate"], done_months)
        except Exception as e:
            logger.error(f"Ошибка расчета графика для ребенка ID {child_id}: {e}")
            continue

        emoji = "👧" if ch.get("gender") == "girl" else "👦"

        for c in schedule:
            if c["is_done"]:
                continue

            # Если осмотр СЕГОДНЯ
            if c["days_diff"] == 0:
                try:
                    family_ids = db.get_family_user_ids(user_id)
                except Exception:
                    family_ids = [user_id]

                for uid in family_ids:
                    try:
                        await app.bot.send_message(
                            chat_id=uid,
                            text=(
                                f"🏥 *Сегодня плановый осмотр!*\n\n"
                                f"{emoji} {ch['name']} — *{c['name']}*\n\n"
                                f"Не забудьте взять полис и карту ребёнка!"
                            ),
                            parse_mode="Markdown"
                        )
                        await asyncio.sleep(0.05)  # Защитная пауза 1/20 секунды
                    except Exception as e:
                        logger.warning(f"Не удалось отправить сообщение пользователю {uid}: {e}")

            # Если осмотр ЧЕРЕЗ 3 ДНЯ
            elif c["days_diff"] == 3:
                try:
                    family_ids = db.get_family_user_ids(user_id)
                except Exception:
                    family_ids = [user_id]

                for uid in family_ids:
                    try:
                        await app.bot.send_message(
                            chat_id=uid,
                            text=(
                                f"🏥 *Через 3 дня плановый осмотр*\n\n"
                                f"{emoji} {ch['name']} — *{c['name']}*\n"
                                f"📅 {c['date']}\n\n"
                                f"Запишитесь к педиатру заранее!"
                            ),
                            parse_mode="Markdown"
                        )
                        await asyncio.sleep(0.05)  # Защитная пауза 1/20 секунды
                    except Exception as e:
                        logger.warning(f"Не удалось отправить сообщение пользователю {uid}: {e}")
