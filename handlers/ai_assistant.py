"""
ИИ-ассистент МамаБота на Groq (llama-3.3-70b):
1. Анализ фото медицинских документов — объясняет простым языком
2. Персональные советы по возрасту ребёнка
"""
import os
import base64
import httpx
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from handlers.child import age_str

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Для анализа изображений — используем vision модель
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Состояния диалога анализа документа
AI_WAIT_DOC = range(90, 91)


# ── Вспомогательные функции ──────────────────────────────────────────────────

async def _ask_groq_text(system: str, user: str, max_tokens: int = 1500) -> str:
    """Текстовый запрос к Groq."""
    if not GROQ_API_KEY:
        return "⚠️ ИИ-функции не настроены. Администратор должен добавить GROQ_API_KEY в переменные окружения Railway."

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_TEXT_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(GROQ_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        return "⏱ ИИ не успел ответить. Попробуйте ещё раз."
    except Exception as e:
        err = str(e)
        if GROQ_API_KEY in err:
            err = err.replace(GROQ_API_KEY, "***")
        return f"❌ Не удалось получить ответ от ИИ. Попробуйте позже."


async def _ask_groq_vision(system: str, user_text: str, image_b64: str, mime: str = "image/jpeg", max_tokens: int = 1500) -> str:
    """Запрос с изображением к Groq vision модели."""
    if not GROQ_API_KEY:
        return "⚠️ ИИ-функции не настроены. Добавьте GROQ_API_KEY в Railway."

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_VISION_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{image_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": user_text
                    }
                ]
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(GROQ_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        return "⏱ ИИ не успел ответить. Попробуйте ещё раз."
    except Exception as e:
        err = str(e)
        if GROQ_API_KEY in err:
            err = err.replace(GROQ_API_KEY, "***")
        return "❌ Не удалось получить ответ от ИИ. Попробуйте позже."


def _months_from_birthdate(birthdate_str: str) -> int:
    try:
        bd = datetime.strptime(birthdate_str, "%d.%m.%Y").date()
    except Exception:
        try:
            bd = date.fromisoformat(birthdate_str)
        except Exception:
            return 0
    today = date.today()
    months = (today.year - bd.year) * 12 + today.month - bd.month
    if today.day < bd.day:
        months -= 1
    return max(0, months)


# ── 1. Анализ медицинских документов ────────────────────────────────────────

async def show_ai_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if query:
        await query.answer()

    children = db.get_children(user_id)
    keyboard = [
        [InlineKeyboardButton("🔬 Анализ медицинского документа", callback_data="ai_analyze_doc")],
    ]
    if children:
        for ch in children:
            emoji = "👧" if ch["gender"] == "girl" else "👦"
            age = age_str(ch["birthdate"])
            keyboard.append([InlineKeyboardButton(
                f"💡 Советы для {ch['name']} ({age})",
                callback_data=f"ai_advice:{ch['id']}"
            )])

    text = (
        "🤖 *ИИ-ассистент МамаБота*\n\n"
        "Выберите что хотите сделать:\n\n"
        "🔬 *Анализ документов* — сфотографируй результаты анализов или выписку, "
        "ИИ объяснит простым языком что значат цифры\n\n"
        "💡 *Советы по возрасту* — персональные рекомендации для вашего ребёнка "
        "на основе его возраста"
    )
    markup = InlineKeyboardMarkup(keyboard)
    if query:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def start_analyze_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔬 *Анализ медицинского документа*\n\n"
        "Пришли мне фото:\n"
        "📸 Сфотографируй результат анализа, выписку или справку\n\n"
        "ИИ объяснит простым языком что означают цифры и термины.\n\n"
        "⚠️ _Это информационная помощь, не замена врачу._\n\n"
        "Отправь фото или /cancel для отмены:",
        parse_mode="Markdown"
    )
    return AI_WAIT_DOC


async def got_document_for_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message

    children = db.get_children(user_id)
    child_context = ""
    if children:
        ch = children[0]
        months = _months_from_birthdate(ch["birthdate"])
        child_context = f"Ребёнок: {ch['name']}, возраст {months} месяцев."

    system_prompt = (
        "Ты добрый и понятный помощник для мам. Объясняешь медицинские документы "
        "простым языком, без страшных терминов. "
        "Когда мама присылает фото с результатами анализов или выпиской — "
        "объясняй: что это за документ, что означают показатели, какие в норме, "
        "какие требуют внимания, что обычно делают в таких случаях. "
        "Всегда в конце напоминай: окончательный вывод делает только врач. "
        "Пиши на русском языке, тепло и по-человечески. Используй эмодзи. "
        + (f"Контекст: {child_context}" if child_context else "")
    )

    thinking_msg = await msg.reply_text("🔍 Изучаю документ, подождите немного...")

    try:
        if msg.photo:
            photo = msg.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()
            b64 = base64.standard_b64encode(bytes(file_bytes)).decode()

            answer = await _ask_groq_vision(
                system=system_prompt,
                user_text="Объясни что написано в этом медицинском документе простым языком.",
                image_b64=b64,
                mime="image/jpeg",
                max_tokens=2000,
            )
        elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
            file = await context.bot.get_file(msg.document.file_id)
            file_bytes = await file.download_as_bytearray()
            b64 = base64.standard_b64encode(bytes(file_bytes)).decode()
            answer = await _ask_groq_vision(
                system=system_prompt,
                user_text="Объясни что написано в этом медицинском документе простым языком.",
                image_b64=b64,
                mime=msg.document.mime_type,
                max_tokens=2000,
            )
        else:
            await thinking_msg.edit_text(
                "⚠️ Пришли фото с медицинским документом.\n\n"
                "PDF к сожалению не поддерживается — просто сфотографируй документ."
            )
            return AI_WAIT_DOC

        keyboard = [
            [InlineKeyboardButton("🔬 Ещё один документ", callback_data="ai_analyze_doc")],
            [InlineKeyboardButton("◀️ Меню ИИ", callback_data="ai_menu")],
        ]
        full_text = f"🔬 *Разбор документа:*\n\n{answer}"
        if len(full_text) > 4000:
            full_text = full_text[:3990] + "..."

        await thinking_msg.edit_text(
            full_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        await thinking_msg.edit_text("❌ Не удалось обработать файл. Попробуйте ещё раз.")

    return ConversationHandler.END


async def cancel_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ── 2. Персональные советы по возрасту ──────────────────────────────────────

async def show_ai_advice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return

    months = _months_from_birthdate(ch["birthdate"])
    age = age_str(ch["birthdate"])
    emoji = "👧" if ch["gender"] == "girl" else "👦"
    gender_word = "девочка" if ch["gender"] == "girl" else "мальчик"

    allergies = db.get_allergies(child_id)
    allergy_names = [a["name"] for a in allergies] if allergies else []
    allergy_context = f"Известные аллергии: {', '.join(allergy_names)}." if allergy_names else ""

    growth = db.get_growth_records(child_id, user_id, limit=1)
    growth_context = ""
    if growth:
        last = growth[0]
        parts_list = []
        if last["height_cm"]:
            parts_list.append(f"рост {last['height_cm']} см")
        if last["weight_kg"]:
            parts_list.append(f"вес {last['weight_kg']} кг")
        if parts_list:
            growth_context = f"Последние замеры: {', '.join(parts_list)}."

    system_prompt = (
        "Ты заботливый и опытный помощник для мам, как подруга-педиатр. "
        "Даёшь тёплые, практичные советы на основе возраста ребёнка. "
        "Пиши по-русски, дружелюбно, с эмодзи. Не пугай маму. "
        "Советы конкретные и применимые прямо сейчас."
    )

    user_prompt = (
        f"Ребёнок: {ch['name']}, {gender_word}, возраст {months} месяцев ({age}). "
        f"{growth_context} {allergy_context}\n\n"
        f"Дай персональные советы для этого возраста:\n"
        f"1. 🥣 Питание — что вводить, что важно в {months} месяцев\n"
        f"2. 🧠 Развитие — что умеют дети в этом возрасте, во что играть\n"
        f"3. 😴 Сон — нормы сна для этого возраста\n"
        f"4. 🏥 На что обратить внимание педиатру\n"
        f"5. 💡 Один практичный лайфхак для мамы\n\n"
        f"Пиши тепло, как подруга которая в этом разбирается."
    )

    await query.edit_message_text(
        f"{emoji} *Готовлю советы для {ch['name']}...*\n\n⏳ Секунду...",
        parse_mode="Markdown"
    )

    answer = await _ask_groq_text(
        system=system_prompt,
        user=user_prompt,
        max_tokens=2000,
    )

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить советы", callback_data=f"ai_advice:{child_id}")],
        [InlineKeyboardButton("◀️ Меню ИИ", callback_data="ai_menu")],
    ]

    full_text = f"{emoji} *Советы для {ch['name']} ({age}):*\n\n{answer}"
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "..."

    await query.edit_message_text(
        full_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
