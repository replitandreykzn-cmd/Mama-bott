"""
Режим «Ожидание малыша» — для беременных.
Пользователь вводит ПДР (предполагаемую дату родов),
бот показывает текущую неделю беременности и советы.
"""
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db

PREG_DATE = range(50, 51)

# Советы по неделям (укороченные, по триместрам)
WEEK_TIPS = {
    # 1й триместр
    range(1, 5):   ("🌱", "Эмбрион формируется. Начните принимать фолиевую кислоту если ещё нет."),
    range(5, 9):   ("💓", "Уже бьётся сердечко! Первый визит к гинекологу и сдача анализов."),
    range(9, 13):  ("🫘", "Малыш размером с финик. Время первого УЗИ (10-12 неделя)."),
    range(13, 17): ("🍋", "Второй триместр! Самочувствие улучшается. Можно сообщить о беременности."),
    # 2й триместр
    range(17, 21): ("🥑", "Малыш начинает двигаться. Скоро почувствуете первые толчки!"),
    range(21, 25): ("🌽", "Второй скрининг (18-21 неделя). Узнайте пол если хотите!"),
    range(25, 29): ("🥦", "Малыш открывает глазки. Начните курсы для беременных."),
    range(29, 33): ("🎃", "Третий триместр! Малыш активно набирает вес. Декретный отпуск."),
    # 3й триместр
    range(33, 37): ("🍉", "Готовьте сумку в роддом! Малыш принимает позицию для родов."),
    range(37, 41): ("👶", "Доношенный малыш! Роды могут начаться в любой момент. Вы готовы!"),
    range(41, 43): ("⏰", "Переношенная беременность. Врач решит о стимуляции. Всё будет хорошо!"),
}

# Что собрать в роддом (показывается с 35 недели)
HOSPITAL_BAG = """📦 *Что взять в роддом:*

*Документы:*
• Паспорт
• Полис ОМС
• Обменная карта
• Родовой сертификат

*Маме:*
• Халат и ночная рубашка (2 шт)
• Тапочки резиновые
• Носки тёплые
• Прокладки послеродовые
• Одноразовые трусы
• Бюстгальтер для кормления
• Зарядник для телефона
• Еда и вода

*Малышу:*
• Бодики и ползунки (3-5 шт)
• Шапочки (2-3 шт)
• Носочки (3 пары)
• Подгузники (1 пачка)
• Влажные салфетки
• Конверт или одеяло на выписку"""


def get_week_from_pdr(pdr_str: str):
    """Вычисляет текущую неделю беременности по ПДР."""
    try:
        pdr = datetime.strptime(pdr_str, "%d.%m.%Y").date()
    except Exception:
        return None, None
    # Беременность = 280 дней (40 недель)
    conception = pdr - __import__('datetime').timedelta(days=280)
    today = date.today()
    days_pregnant = (today - conception).days
    if days_pregnant < 0:
        return None, None
    week = days_pregnant // 7 + 1
    days_in_week = days_pregnant % 7
    return week, days_in_week


def get_tip_for_week(week: int):
    for week_range, (emoji, tip) in WEEK_TIPS.items():
        if week in week_range:
            return emoji, tip
    return "🌸", "Берегите себя и малыша!"


async def show_pregnancy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    is_cb = query is not None

    if is_cb:
        await query.answer()

    pdr = db.get_pregnancy_pdr(user_id)

    if not pdr:
        keyboard = [
            [InlineKeyboardButton("🤰 Ввести ПДР", callback_data="preg_set_pdr")],
        ]
        text = (
            "🤰 *Режим «Ожидание малыша»*\n\n"
            "Введи предполагаемую дату родов (ПДР) — и я буду:\n"
            "• Показывать текущую неделю беременности\n"
            "• Давать советы по каждой неделе\n"
            "• Напоминать о важных анализах и УЗИ\n"
            "• Подсказывать что взять в роддом\n\n"
            "ПДР обычно говорит гинеколог на первом приёме."
        )
    else:
        week, days = get_week_from_pdr(pdr)
        if week is None or week > 42:
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить ПДР", callback_data="preg_set_pdr")],
                [InlineKeyboardButton("👶 Малыш родился!", callback_data="preg_born")],
            ]
            text = (
                "🤰 *Ожидание малыша*\n\n"
                f"📅 ПДР: {pdr}\n\n"
                "Похоже малыш уже родился или скоро появится! 🎉\n"
                "Нажми «Малыш родился!» чтобы добавить ребёнка в бот."
            )
        else:
            emoji, tip = get_tip_for_week(week)
            trimester = "I триместр" if week <= 12 else ("II триместр" if week <= 26 else "III триместр")
            days_left = (datetime.strptime(pdr, "%d.%m.%Y").date() - date.today()).days

            text = (
                f"🤰 *Ожидание малыша*\n\n"
                f"{emoji} *{week} неделя беременности* ({trimester})\n"
                f"День {days + 1} из 7\n\n"
                f"📅 ПДР: {pdr}\n"
                f"⏳ До родов: примерно {max(0, days_left)} дн.\n\n"
                f"💡 *Совет недели:*\n{tip}"
            )
            if week >= 35:
                text += "\n\n" + HOSPITAL_BAG

            keyboard = [
                [InlineKeyboardButton("📋 Что взять в роддом", callback_data="preg_bag")],
                [InlineKeyboardButton("🔄 Обновить ПДР", callback_data="preg_set_pdr")],
                [InlineKeyboardButton("👶 Малыш родился!", callback_data="preg_born")],
            ]

    markup = InlineKeyboardMarkup(keyboard)
    if is_cb:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def show_hospital_bag_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="pregnancy")]]
    await query.edit_message_text(
        HOSPITAL_BAG,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start_set_pdr_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🤰 *Введите ПДР*\n\n"
        "Введите предполагаемую дату родов в формате ДД.ММ.ГГГГ\n"
        "(например: 15.09.2025)\n\n"
        "ПДР указана в обменной карте или скажет гинеколог.",
        parse_mode="Markdown"
    )
    return PREG_DATE


async def got_pdr_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        pdr = datetime.strptime(text, "%d.%m.%Y")
        # ПДР должна быть в будущем или не более 9 месяцев назад
        from datetime import timedelta
        if pdr.date() < date.today() - __import__('datetime').timedelta(days=280):
            await update.message.reply_text(
                "Дата слишком далеко в прошлом. Введите корректную ПДР:"
            )
            return PREG_DATE
    except ValueError:
        await update.message.reply_text(
            "Неверный формат. Введите дату в виде ДД.ММ.ГГГГ (например 15.09.2025):"
        )
        return PREG_DATE

    user_id = update.effective_user.id
    db.set_pregnancy_pdr(user_id, text)

    week, days = get_week_from_pdr(text)
    keyboard = [[InlineKeyboardButton("🤰 К беременности", callback_data="pregnancy")]]

    if week and 1 <= week <= 42:
        emoji, tip = get_tip_for_week(week)
        await update.message.reply_text(
            f"✅ ПДР сохранена: *{text}*\n\n"
            f"{emoji} Сейчас у вас *{week} неделя беременности*.\n\n"
            f"💡 {tip}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            f"✅ ПДР сохранена: *{text}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    return ConversationHandler.END


async def pregnancy_born_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Малыш родился — предлагаем добавить ребёнка."""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("👶 Добавить ребёнка", callback_data="child_add")],
        [InlineKeyboardButton("◀️ Назад", callback_data="pregnancy")],
    ]
    await query.edit_message_text(
        "🎉 *Поздравляем с рождением малыша!*\n\n"
        "Добавьте ребёнка в бот — и я помогу следить за прививками, "
        "ростом и здоровьем!\n\n"
        "После добавления ребёнка режим беременности можно отключить в настройках.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_preg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

