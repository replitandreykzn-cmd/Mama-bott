"""
ИИ-ассистент МамаБота на Google Gemini:
1. Анализ фото/PDF медицинских документов — объясняет простым языком
2. Персональные советы по возрасту ребёнка
"""
import os
import base64
import asyncio
import httpx
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from handlers.child import age_str

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Состояния диалога анализа документа
AI_WAIT_DOC = range(90, 91)


# ── Вспомогательная функция запроса к Gemini ────────────────────────────────

async def _ask_gemini(parts: list, system: str, max_tokens: int = 1500) -> str:
    """Отправляет запрос к Gemini API, при ошибке 429 делает 2 повтора."""
    if not GEMINI_API_KEY:
        return (
            "⚠️ ИИ-функции не настроены.\n"
            "Администратор должен добавить GEMINI_API_KEY в переменные окружения Railway."
        )

    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"

    payload = {
        "system_instruction": {
            "parts": [{"text": system}]
        },
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
        }
    }

    last_error = None
    for attempt in range(3):  # 3 попытки
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)

                if resp.status_code == 429:
                    # Подождать и попробовать снова
                    wait = 5 * (attempt + 1)  # 5с, 10с, 15с
                    await asyncio.sleep(wait)
                    last_error = "429"
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]

        except httpx.TimeoutException:
            last_error = "timeout"
            await asyncio.sleep(3)
            continue
        except Exception as e:
            # Убираем ключ из текста ошибки перед показом
            err_text = str(e)
            if GEMINI_API_KEY and GEMINI_API_KEY in err_text:
                err_text = err_text.replace(GEMINI_API_KEY, "***")
            last_error = err_text
            break

    # Все попытки исчерпаны
    if last_error == "429":
        return (
            "⏳ ИИ сейчас перегружен — слишком много запросов.\n\n"
            "Подождите 30 секунд и попробуйте снова."
        )
    elif last_error == "timeout":
        return (
            "⏱ ИИ не успел ответить.\n\n"
            "Попробуйте ещё раз — обычно со второй попытки работает."
        )
    else:
        return f"❌ Не удалось получить ответ от ИИ. Попробуйте позже."


def _months_from_birthdate(birthdate_str: str) -> int:
    """Возвращает возраст ребёнка в месяцах."""
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
    """Главное меню ИИ-ассистента."""
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
    """Начало диалога анализа документа — просим прислать фото или PDF."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔬 *Анализ медицинского документа*\n\n"
        "Пришли мне:\n"
        "📸 *Фото* — сфотографируй результат анализа, выписку или справку\n"
        "📄 *PDF-файл* — прикрепи документ из памяти телефона\n\n"
        "ИИ объяснит простым языком что означают цифры и термины.\n\n"
        "⚠️ _Это информационная помощь, не замена врачу._\n\n"
        "Отправь документ или /cancel для отмены:",
        parse_mode="Markdown"
    )
    return AI_WAIT_DOC


async def got_document_for_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили фото или PDF — анализируем через Gemini."""
    user_id = update.effective_user.id
    msg = update.message

    # Получаем контекст ребёнка если есть
    children = db.get_children(user_id)
    child_context = ""
    if children:
        ch = children[0]
        months = _months_from_birthdate(ch["birthdate"])
        child_context = f"Ребёнок: {ch['name']}, возраст {months} месяцев."

    system_prompt = (
        "Ты добрый и понятный помощник для мам. Твоя задача — объяснять медицинские документы "
        "простым языком, без страшных терминов. "
        "Когда мама присылает фото или PDF с результатами анализов, выпиской или справкой — "
        "ты объясняешь: что это за документ, что означают показатели, какие в норме, "
        "какие требуют внимания, и что обычно делают в таких случаях. "
        "Всегда в конце напоминай: окончательный вывод делает только врач. "
        "Пиши на русском языке, тепло и по-человечески. Используй эмодзи для наглядности. "
        + (f"Контекст: {child_context}" if child_context else "")
    )

    thinking_msg = await msg.reply_text("🔍 Изучаю документ, подождите немного...")

    try:
        parts = []

        if msg.photo:
            photo = msg.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()
            b64 = base64.standard_b64encode(bytes(file_bytes)).decode()
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
            parts.append({"text": "Объясни что написано в этом медицинском документе простым языком."})

        elif msg.document:
            doc = msg.document
            mime = doc.mime_type or ""

            if "pdf" in mime:
                file = await context.bot.get_file(doc.file_id)
                file_bytes = await file.download_as_bytearray()
                b64 = base64.standard_b64encode(bytes(file_bytes)).decode()
                parts.append({"inline_data": {"mime_type": "application/pdf", "data": b64}})
                parts.append({"text": "Объясни что написано в этом медицинском документе простым языком."})

            elif mime.startswith("image/"):
                file = await context.bot.get_file(doc.file_id)
                file_bytes = await file.download_as_bytearray()
                b64 = base64.standard_b64encode(bytes(file_bytes)).decode()
                parts.append({"inline_data": {"mime_type": mime, "data": b64}})
                parts.append({"text": "Объясни что написано в этом медицинском документе простым языком."})

            else:
                await thinking_msg.edit_text(
                    "⚠️ Поддерживаются только фото и PDF-файлы. Пришли фото или PDF-документ."
                )
                return AI_WAIT_DOC
        else:
            await thinking_msg.edit_text("⚠️ Пришли фото или PDF-файл с медицинским документом.")
            return AI_WAIT_DOC

        answer = await _ask_gemini(parts=parts, system=system_prompt, max_tokens=2000)

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

    except Exception as e:
        await thinking_msg.edit_text("❌ Не удалось обработать файл. Попробуйте ещё раз.")

    return ConversationHandler.END


async def cancel_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ── 2. Персональные советы по возрасту ──────────────────────────────────────

async def show_ai_advice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует персональные советы для конкретного ребёнка."""
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
        "Советы должны быть конкретными и применимыми прямо сейчас."
    )

    user_prompt = (
        f"Ребёнок: {ch['name']}, {gender_word}, возраст {months} месяцев ({age}). "
        f"{growth_context} {allergy_context}\n\n"
        f"Дай персональные советы для этого возраста по следующим темам:\n"
        f"1. 🥣 Питание — что вводить, что важно в этом возрасте\n"
        f"2. 🧠 Развитие — что умеют дети в {months} месяцев, во что играть\n"
        f"3. 😴 Сон — нормы сна для этого возраста\n"
        f"4. 🏥 На что обратить внимание — что важно проверить у педиатра\n"
        f"5. 💡 Лайфхак для мамы — один практичный совет\n\n"
        f"Пиши тепло, как подруга которая в этом разбирается."
    )

    await query.edit_message_text(
        f"{emoji} *Готовлю советы для {ch['name']}...*\n\n⏳ Секунду...",
        parse_mode="Markdown"
    )

    answer = await _ask_gemini(
        parts=[{"text": user_prompt}],
        system=system_prompt,
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
