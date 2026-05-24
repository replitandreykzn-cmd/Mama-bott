import io
import os
from datetime import date, datetime

from fpdf import FPDF
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from handlers.child import age_str

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
FONT_PATH = os.path.join(FONT_DIR, "DejaVuSans.ttf")

# Цветовая палитра
C_PINK       = (220, 80, 120)
C_PINK_LIGHT = (255, 235, 245)
C_PINK_MID   = (255, 210, 230)
C_BLUE       = (70, 130, 200)
C_BLUE_LIGHT = (235, 245, 255)
C_BLUE_MID   = (210, 230, 255)
C_GREEN      = (60, 160, 80)
C_GREEN_LIGHT= (235, 255, 240)
C_GREEN_MID  = (200, 240, 210)
C_ORANGE     = (200, 100, 20)
C_ORANGE_LIGHT=(255, 248, 235)
C_ORANGE_MID = (255, 225, 180)
C_PURPLE     = (120, 80, 200)
C_PURPLE_LIGHT=(245, 240, 255)
C_PURPLE_MID = (220, 210, 255)
C_GRAY_DARK  = (60, 60, 60)
C_GRAY_MID   = (120, 120, 120)
C_GRAY_LIGHT = (245, 245, 245)
C_WHITE      = (255, 255, 255)
C_RED        = (200, 50, 50)


def _ensure_font():
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"Шрифт не найден: {FONT_PATH}")


def _set_color(pdf, color, fill=False):
    if fill:
        pdf.set_fill_color(*color)
    else:
        pdf.set_text_color(*color)


def _section_header(pdf, title, icon, bg, text_color):
    pdf.ln(4)
    pdf.set_fill_color(*bg)
    pdf.set_draw_color(*text_color)
    pdf.set_line_width(0.5)
    pdf.rect(10, pdf.get_y(), 190, 11, "FD")
    pdf.set_font("DejaVu", "B", 12)
    pdf.set_text_color(*text_color)
    pdf.cell(0, 11, f"  {icon}  {title}", ln=True)
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.2)
    pdf.ln(3)


def _divider(pdf, color=None):
    color = color or C_GRAY_MID
    pdf.set_draw_color(*color)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)


def _info_row(pdf, label, value, label_color=None, value_color=None):
    label_color = label_color or C_GRAY_MID
    value_color = value_color or C_GRAY_DARK
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*label_color)
    pdf.cell(52, 7, label)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(*value_color)
    pdf.cell(0, 7, value, ln=True)


def generate_child_pdf(child, growth_records, vaccinations, illnesses=None, medications=None) -> bytes:
    _ensure_font()

    pdf = FPDF()
    pdf.add_font("DejaVu", "", FONT_PATH)
    pdf.add_font("DejaVu", "B", FONT_PATH)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(10, 10, 10)

    gender_str = "Девочка" if child["gender"] == "girl" else "Мальчик"
    gender_icon = "♀" if child["gender"] == "girl" else "♂"
    age = age_str(child["birthdate"])

    # ── ШАПКА ────────────────────────────────────────────────────────────────
    # Розовый фон
    pdf.set_fill_color(*C_PINK)
    pdf.rect(0, 0, 210, 38, "F")

    # Декоративная полоска снизу шапки
    pdf.set_fill_color(180, 50, 90)
    pdf.rect(0, 35, 210, 3, "F")

    pdf.set_font("DejaVu", "B", 20)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 12, "", ln=True)
    pdf.cell(0, 12, "МамаБот", align="C", ln=True)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(255, 220, 235)
    pdf.cell(0, 7, "Медицинский отчёт для педиатра", align="C", ln=True)
    pdf.ln(8)

    # ── КАРТОЧКА РЕБЁНКА ─────────────────────────────────────────────────────
    # Белая карточка с тенью
    pdf.set_fill_color(*C_PINK_LIGHT)
    pdf.set_draw_color(*C_PINK)
    pdf.set_line_width(0.8)
    y_card = pdf.get_y()
    pdf.rect(10, y_card, 190, 42, "FD")

    # Цветная полоска слева
    pdf.set_fill_color(*C_PINK)
    pdf.rect(10, y_card, 4, 42, "F")

    pdf.set_xy(18, y_card + 5)
    pdf.set_font("DejaVu", "B", 16)
    pdf.set_text_color(*C_PINK)
    pdf.cell(0, 10, f"{gender_icon}  {child['name']}", ln=True)

    pdf.set_x(18)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(*C_GRAY_MID)
    pdf.cell(60, 7, "Дата рождения:")
    pdf.set_text_color(*C_GRAY_DARK)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(0, 7, child["birthdate"], ln=True)

    pdf.set_x(18)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(*C_GRAY_MID)
    pdf.cell(60, 7, "Возраст:")
    pdf.set_text_color(*C_PINK)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(0, 7, age, ln=True)

    pdf.set_x(18)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(*C_GRAY_MID)
    pdf.cell(60, 7, "Пол:")
    pdf.set_text_color(*C_GRAY_DARK)
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 7, gender_str, ln=True)

    # Дата создания справа
    pdf.set_xy(140, y_card + 5)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*C_GRAY_MID)
    pdf.cell(55, 6, f"Создан: {date.today().strftime('%d.%m.%Y')}", align="R", ln=True)

    pdf.set_y(y_card + 46)

    # ── РОСТ И ВЕС ───────────────────────────────────────────────────────────
    _section_header(pdf, "Рост и вес", "◉", C_BLUE_MID, C_BLUE)

    if growth_records:
        # Заголовок таблицы
        pdf.set_fill_color(*C_BLUE)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(60, 8, "  Дата", fill=True)
        pdf.cell(60, 8, "Рост (см)", fill=True, align="C")
        pdf.cell(60, 8, "Вес (кг)", fill=True, align="C", ln=True)

        for i, r in enumerate(growth_records):
            if i % 2 == 0:
                pdf.set_fill_color(*C_BLUE_LIGHT)
            else:
                pdf.set_fill_color(*C_WHITE)
            pdf.set_text_color(*C_GRAY_DARK)
            pdf.set_font("DejaVu", "", 10)
            pdf.cell(60, 7, f"  {r['date']}", fill=True)
            h = str(r["height_cm"]) if r["height_cm"] else "—"
            w = str(r["weight_kg"]) if r["weight_kg"] else "—"
            pdf.set_font("DejaVu", "B", 10)
            pdf.set_text_color(*C_BLUE)
            pdf.cell(60, 7, h, fill=True, align="C")
            pdf.cell(60, 7, w, fill=True, align="C", ln=True)

        # Итог — последний замер
        last = growth_records[0]
        pdf.set_fill_color(*C_BLUE_MID)
        pdf.set_text_color(*C_BLUE)
        pdf.set_font("DejaVu", "B", 9)
        h_last = f"{last['height_cm']} см" if last["height_cm"] else "—"
        w_last = f"{last['weight_kg']} кг" if last["weight_kg"] else "—"
        pdf.cell(0, 7, f"  Последний замер: {last['date']}  —  рост {h_last}, вес {w_last}", fill=True, ln=True)
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*C_GRAY_MID)
        pdf.cell(0, 8, "  Записи отсутствуют", ln=True)

    # ── ПРИВИВКИ ─────────────────────────────────────────────────────────────
    _section_header(pdf, "Прививки", "✦", C_GREEN_MID, C_GREEN)

    if vaccinations:
        done = [v for v in vaccinations if v["done_date"]]
        pending = [v for v in vaccinations if not v["done_date"]]
        overdue = []
        for v in pending:
            if v["scheduled_date"]:
                try:
                    if datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date() <= date.today():
                        overdue.append(v)
                except Exception:
                    pass

        # Статистика прививок — три блока
        pdf.set_fill_color(*C_GREEN_MID)
        pdf.set_text_color(*C_GREEN)
        pdf.set_font("DejaVu", "B", 10)
        w3 = 62
        pdf.cell(w3, 9, f"  Сделано: {len(done)}", fill=True, align="L")
        pdf.set_fill_color(*C_ORANGE_MID)
        pdf.set_text_color(*C_ORANGE)
        pdf.cell(w3, 9, f"Просрочено: {len(overdue)}", fill=True, align="C")
        pdf.set_fill_color(*C_BLUE_MID)
        pdf.set_text_color(*C_BLUE)
        pdf.cell(w3+4, 9, f"Предстоит: {len(pending)-len(overdue)}", fill=True, align="C", ln=True)
        pdf.ln(2)

        # Таблица
        pdf.set_fill_color(*C_GREEN)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("DejaVu", "B", 9)
        pdf.cell(100, 8, "  Прививка", fill=True)
        pdf.cell(40, 8, "Статус", fill=True, align="C")
        pdf.cell(50, 8, "Дата / план", fill=True, align="C", ln=True)

        pdf.set_font("DejaVu", "", 9)
        for i, v in enumerate(vaccinations):
            bg = C_GREEN_LIGHT if i % 2 == 0 else C_WHITE
            pdf.set_fill_color(*bg)

            if v["done_date"]:
                status = "✓ Сделано"
                status_color = C_GREEN
                date_val = v["done_date"]
            else:
                try:
                    d = datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date()
                    if d <= date.today():
                        status = "! Просрочено"
                        status_color = C_RED
                    else:
                        status = "→ Предстоит"
                        status_color = C_BLUE
                except Exception:
                    status = "→ Предстоит"
                    status_color = C_BLUE
                date_val = v["scheduled_date"] or "—"

            name_text = v["vaccine_name"]
            if len(name_text) > 52:
                name_text = name_text[:50] + ".."

            pdf.set_text_color(*C_GRAY_DARK)
            pdf.cell(100, 6, f"  {name_text}", fill=True)
            pdf.set_text_color(*status_color)
            pdf.set_font("DejaVu", "B", 9)
            pdf.cell(40, 6, status, fill=True, align="C")
            pdf.set_text_color(*C_GRAY_DARK)
            pdf.set_font("DejaVu", "", 9)
            pdf.cell(50, 6, date_val, fill=True, align="C", ln=True)
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*C_GRAY_MID)
        pdf.cell(0, 8, "  Прививки не добавлены", ln=True)

    # ── ИСТОРИЯ БОЛЕЗНЕЙ ─────────────────────────────────────────────────────
    _section_header(pdf, "История болезней", "♥", C_ORANGE_MID, C_ORANGE)

    if illnesses:
        for ill in illnesses:
            end = ill["end_date"] or "не закрыта"
            is_active = not ill["end_date"]

            # Заголовок болезни
            bg = C_ORANGE_MID if is_active else C_ORANGE_LIGHT
            pdf.set_fill_color(*bg)
            pdf.set_text_color(*C_ORANGE)
            pdf.set_font("DejaVu", "B", 10)
            status_mark = " ● АКТИВНО" if is_active else ""
            pdf.cell(0, 8, f"  {ill['illness_name']}   ({ill['start_date']} — {end}){status_mark}", fill=True, ln=True)

            entries = db.get_illness_entries(ill["id"])
            if entries:
                pdf.set_fill_color(*C_ORANGE)
                pdf.set_text_color(*C_WHITE)
                pdf.set_font("DejaVu", "B", 8)
                pdf.cell(32, 6, "  Дата", fill=True)
                pdf.cell(22, 6, "Темп.", fill=True, align="C")
                pdf.cell(68, 6, "Симптомы", fill=True, align="C")
                pdf.cell(68, 6, "Лекарства", fill=True, align="C", ln=True)

                for i, e in enumerate(entries):
                    bg2 = C_ORANGE_LIGHT if i % 2 == 0 else C_WHITE
                    pdf.set_fill_color(*bg2)
                    pdf.set_text_color(*C_GRAY_DARK)
                    pdf.set_font("DejaVu", "", 8)
                    temp = f"{e['temperature']}°" if e["temperature"] else "—"
                    symp = (e["symptoms"] or "—")[:35]
                    meds = (e["medications_given"] or "—")[:38]
                    pdf.cell(32, 6, f"  {e['entry_date']}", fill=True)
                    pdf.set_text_color(*C_RED if e["temperature"] and float(e["temperature"]) >= 38 else C_GRAY_DARK)
                    pdf.cell(22, 6, temp, fill=True, align="C")
                    pdf.set_text_color(*C_GRAY_DARK)
                    pdf.cell(68, 6, symp, fill=True)
                    pdf.cell(68, 6, meds, fill=True, ln=True)
            pdf.ln(3)
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*C_GRAY_MID)
        pdf.cell(0, 8, "  Болезни не записаны", ln=True)

    # ── ЛЕКАРСТВА ────────────────────────────────────────────────────────────
    _section_header(pdf, "Лекарства", "✚", C_PURPLE_MID, C_PURPLE)

    if medications:
        pdf.set_fill_color(*C_PURPLE)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("DejaVu", "B", 9)
        pdf.cell(60, 8, "  Название", fill=True)
        pdf.cell(38, 8, "Доза", fill=True, align="C")
        pdf.cell(38, 8, "Интервал", fill=True, align="C")
        pdf.cell(54, 8, "До даты", fill=True, align="C", ln=True)

        for i, m in enumerate(medications):
            bg = C_PURPLE_LIGHT if i % 2 == 0 else C_WHITE
            pdf.set_fill_color(*bg)
            pdf.set_text_color(*C_GRAY_DARK)
            pdf.set_font("DejaVu", "", 9)
            interval = f"каждые {m['interval_hours']}ч"
            pdf.cell(60, 7, f"  {(m['name'] or '')[:30]}", fill=True)
            pdf.set_text_color(*C_PURPLE)
            pdf.set_font("DejaVu", "B", 9)
            pdf.cell(38, 7, (m["dose"] or "—")[:18], fill=True, align="C")
            pdf.set_text_color(*C_GRAY_DARK)
            pdf.set_font("DejaVu", "", 9)
            pdf.cell(38, 7, interval, fill=True, align="C")
            pdf.cell(54, 7, m["end_date"] or "—", fill=True, align="C", ln=True)
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*C_GRAY_MID)
        pdf.cell(0, 8, "  Лекарства не записаны", ln=True)

    # ── ПОДВАЛ ───────────────────────────────────────────────────────────────
    pdf.ln(8)
    pdf.set_fill_color(*C_PINK)
    pdf.rect(0, pdf.get_y(), 210, 12, "F")
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 12, "МамаБот · Отчёт сформирован автоматически · Только для личного использования", align="C", ln=True)

    return bytes(pdf.output())


async def export_pdf_select_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    children = db.get_children(user_id)
    is_callback = query is not None

    if is_callback:
        await query.answer()

    async def send_text(text, keyboard):
        markup = InlineKeyboardMarkup(keyboard)
        if is_callback:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
        else:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)

    if not children:
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child")]]
        await send_text("📄 Нет детей для экспорта. Сначала добавьте ребёнка.", keyboard)
        return

    if len(children) == 1:
        if is_callback:
            await _do_export(query, context, children[0]["id"], user_id)
        else:
            await _do_export_from_message(update.message, context, children[0]["id"], user_id)
        return

    keyboard = []
    for ch in children:
        emoji = "👧" if ch["gender"] == "girl" else "👦"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {ch['name']}", callback_data=f"pdf_export:{ch['id']}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="my_child")])
    await send_text("📄 *Экспорт в PDF*\n\nВыберите ребёнка:", keyboard)


async def export_pdf_for_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Создаю PDF...")
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    await _do_export(query, context, child_id, user_id)


async def _do_export_from_message(message, context, child_id: int, user_id: int):
    ch = db.get_child(child_id, user_id)
    if not ch:
        await message.reply_text("Ребёнок не найден.")
        return

    wait_msg = await message.reply_text("⏳ Создаю PDF-отчёт для педиатра, подождите...")

    growth = db.get_growth_records(child_id, user_id, limit=100)
    vaccines = db.get_vaccinations(child_id, user_id)
    illnesses = db.get_illnesses(child_id, active_only=False, limit=20)
    medications = db.get_medications(child_id, active_only=False)

    try:
        pdf_bytes = generate_child_pdf(ch, growth, vaccines, illnesses, medications)
        buf = io.BytesIO(pdf_bytes)
        buf.name = f"{ch['name']}_отчет.pdf"
        keyboard = [[InlineKeyboardButton("👶 К ребёнку", callback_data=f"child_view:{child_id}")]]
        await message.reply_document(
            document=buf,
            filename=f"{ch['name']}_отчет.pdf",
            caption=f"📄 Полный отчёт для педиатра: {ch['name']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await wait_msg.delete()
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка создания PDF: {e}")


async def _do_export(query, context, child_id: int, user_id: int):
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return

    await query.edit_message_text("⏳ Создаю полный PDF-отчёт для педиатра, подождите...")

    growth = db.get_growth_records(child_id, user_id, limit=100)
    vaccines = db.get_vaccinations(child_id, user_id)
    illnesses = db.get_illnesses(child_id, active_only=False, limit=20)
    medications = db.get_medications(child_id, active_only=False)

    try:
        pdf_bytes = generate_child_pdf(ch, growth, vaccines, illnesses, medications)
        buf = io.BytesIO(pdf_bytes)
        buf.name = f"{ch['name']}_полный_отчет.pdf"

        keyboard = [[InlineKeyboardButton("👶 К ребёнку", callback_data=f"child_view:{child_id}")]]
        await query.message.reply_document(
            document=buf,
            filename=f"{ch['name']}_полный_отчет.pdf",
            caption=f"📄 Полный отчёт для педиатра: {ch['name']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.delete_message()
    except Exception as e:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"child_view:{child_id}")]]
        await query.edit_message_text(
            f"❌ Ошибка создания PDF. Попробуйте позже.\n\n`{e}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
