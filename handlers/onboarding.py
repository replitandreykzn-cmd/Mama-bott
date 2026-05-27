"""
Онбординг для новых пользователей — пошаговое знакомство с ботом.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

STEPS = [
    {
        "title": "Привет! Я МамаБот 🌸",
        "text": (
            "Я твой личный помощник — слежу за здоровьем и развитием ребёнка, "
            "напоминаю о прививках и лекарствах, храню всю историю.\n\n"
            "Мамы говорят: *«Наконец-то всё в одном месте!»* 💛\n\n"
            "Давай быстро покажу что умею — займёт меньше минуты!"
        ),
        "emoji": "🌸",
    },
    {
        "title": "👶 Дети",
        "text": (
            "Добавь ребёнка — и я автоматически создам полный *календарь прививок* "
            "по российскому нацкалендарю.\n\n"
            "Можно добавить несколько детей (Premium)."
        ),
        "emoji": "👶",
    },
    {
        "title": "📏 Рост и вес",
        "text": (
            "Записывай рост и вес ребёнка — я буду хранить всю историю.\n\n"
            "Потом можно выгрузить в PDF или Excel и показать педиатру."
        ),
        "emoji": "📏",
    },
    {
        "title": "💉 Прививки и осмотры",
        "text": (
            "Я слежу за прививками и плановыми осмотрами педиатра.\n\n"
            "За 3 дня до осмотра или прививки — пришлю напоминание, "
            "чтобы ты успела записаться."
        ),
        "emoji": "💉",
    },
    {
        "title": "💊 Лекарства и болезни",
        "text": (
            "Добавь лекарство — и я буду напоминать когда давать следующую дозу.\n\n"
            "В журнале болезней храни температуру, симптомы и что помогло — "
            "пригодится на следующем приёме у врача."
        ),
        "emoji": "💊",
    },
    {
        "title": "🤖 ИИ-ассистент",
        "text": (
            "Сфотографируй результат анализа или выписку — и я объясню "
            "*простым языком* что означают цифры и термины.\n\n"
            "Ещё даю персональные советы по питанию, развитию и сну "
            "исходя из возраста твоего ребёнка. 💡"
        ),
        "emoji": "🤖",
    },
    {
        "title": "📄 PDF и Excel для врача",
        "text": (
            "Одной кнопкой создаю красивый отчёт с прививками, ростом и болезнями.\n\n"
            "Врачи это ценят — не нужно ничего объяснять на словах!"
        ),
        "emoji": "📄",
    },
    {
        "title": "Всё готово! 🎉",
        "text": (
            "Начнём с главного — добавь своего ребёнка!\n\n"
            "После этого все разделы станут доступны."
        ),
        "emoji": "🚀",
    },
]


def _step_keyboard(step: int, total: int):
    buttons = []
    nav = []
    if step > 0:
        nav.append(InlineKeyboardButton("◀️ Назад", callback_data=f"onboard:{step - 1}"))
    if step < total - 1:
        nav.append(InlineKeyboardButton("Далее ▶️", callback_data=f"onboard:{step + 1}"))
    if nav:
        buttons.append(nav)

    if step == total - 1:
        buttons.append([InlineKeyboardButton("👶 Добавить ребёнка", callback_data="child_add")])
        buttons.append([InlineKeyboardButton("⏩ Пропустить", callback_data="onboard_done")])
    else:
        buttons.append([InlineKeyboardButton("⏩ Пропустить", callback_data="onboard_done")])

    return InlineKeyboardMarkup(buttons)


def _step_text(step: int) -> str:
    s = STEPS[step]
    total = len(STEPS)
    progress = "".join("●" if i == step else "○" for i in range(total))
    return (
        f"{s['emoji']} *{s['title']}*\n\n"
        f"{s['text']}\n\n"
        f"_{progress}_"
    )


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает онбординг — вызывается при первом запуске."""
    text = _step_text(0)
    keyboard = _step_keyboard(0, len(STEPS))
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def onboarding_step_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход между шагами онбординга."""
    query = update.callback_query
    await query.answer()
    step = int(query.data.split(":")[1])
    text = _step_text(step)
    keyboard = _step_keyboard(step, len(STEPS))
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def finish_onboarding_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустить / завершить онбординг."""
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="child_add")]]
    await query.edit_message_text(
        "🌸 *МамаБот готов к работе!*\n\n"
        "Начни с добавления ребёнка — нажми кнопку ниже 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
