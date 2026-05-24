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


def _ensure_font():
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"Шрифт не найден: {FONT_PATH}")


def _status_text(r) -> str:
    if r["done_date"]:
        return f"Сделано {r['done_date']}"
    if r["scheduled_date"]:
        try:
            d = datetime.strptime(r["scheduled_date"], "%d.%m.%Y").date()
            if d <= date.today():
                return f"Просрочено (план: {r['scheduled_date']})"
        except Exception:
            pass
        return f"Запланировано: {r['scheduled_date']}"
    return "—"


def generate_child_pdf(child, growth_records, vaccinations) -> bytes:
    _ensure_font()

    pdf = FPDF()
    pdf.add_font("DejaVu", "", FONT_PATH)
    pdf.add_font("DejaVu", "B", FONT_PATH)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    gender_str = "Девочка" if child["gender"] == "girl" else "Мальчик"
    age = age_str(child["birthdate"])
    emoji_char = "♀" if child["gender"] == "girl" else "♂"

    pdf.set_font("DejaVu", "B", 18)
    pdf.set_fill_color(255, 240, 245)
    pdf.rect(0, 0, 210, 40, "F")
    pdf.set_text_color(180, 60, 100)
    pdf.cell(0, 10, "", ln=True)
    pdf.cell(0, 10, f"МамаБот — Карта ребёнка", align="C", ln=True)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Создан: {date.today().strftime('%d.%m.%Y')}", align="C", ln=True)
    pdf.ln(8)

    pdf.set_text_color(40, 40, 40)
    pdf.set_font("DejaVu", "B", 14)
    pdf.set_fill_color(255, 220, 235)
    pdf.cell(0, 10, f"  {emoji_char}  {child['name']}", fill=True, ln=True)
    pdf.ln(2)

    pdf.set_font("DejaVu", "", 11)
    pdf.set_fill_color(250, 250, 250)
    info_rows = [
        ("Дата рождения:", child["birthdate"]),
        ("Возраст:", age),
        ("Пол:", gender_str),
    ]
    for label, value in info_rows:
        pdf.set_font("DejaVu", "B", 11)
        pdf.cell(55, 8, label)
        pdf.set_font("DejaVu", "", 11)
        pdf.cell(0, 8, value, ln=True)
    pdf.ln(6)

    pdf.set_font("DejaVu", "B", 13)
    pdf.set_fill_color(230, 245, 255)
    pdf.cell(0, 9, "  Рост и вес", fill=True, ln=True)
    pdf.ln(2)

    if growth_records:
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_fill_color(210, 235, 255)
        pdf.cell(55, 7, "Дата", fill=True, border=1)
        pdf.cell(45, 7, "Рост (см)", fill=True, border=1)
        pdf.cell(45, 7, "Вес (кг)", fill=True, border=1, ln=True)
        pdf.set_font("DejaVu", "", 10)
        for i, r in enumerate(growth_records):
            fill = i % 2 == 0
            pdf.set_fill_color(248, 248, 248) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.cell(55, 7, str(r["date"]), border=1, fill=fill)
            pdf.cell(45, 7, str(r["height_cm"]) if r["height_cm"] else "—", border=1, fill=fill)
            pdf.cell(45, 7, str(r["weight_kg"]) if r["weight_kg"] else "—", border=1, fill=fill, ln=True)
    else:
        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 8, "Записи отсутствуют", ln=True)
        pdf.set_text_color(40, 40, 40)

    pdf.ln(6)

    pdf.set_font("DejaVu", "B", 13)
    pdf.set_fill_color(230, 255, 235)
    pdf.cell(0, 9, "  Прививки", fill=True, ln=True)
    pdf.ln(2)

    if vaccinations:
        done = [v for v in vaccinations if v["done_date"]]
        pending = [v for v in vaccinations if not v["done_date"]]
        overdue = [v for v in pending if v["scheduled_date"] and
                   datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date() <= date.today()]

        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(60, 140, 60)
        pdf.cell(0, 7, f"Сделано: {len(done)}    Просрочено: {len(overdue)}    Предстоит: {len(pending) - len(overdue)}", ln=True)
        pdf.set_text_color(40, 40, 40)
        pdf.ln(2)

        pdf.set_font("DejaVu", "B", 10)
        pdf.set_fill_color(210, 245, 215)
        pdf.cell(90, 7, "Прививка", fill=True, border=1)
        pdf.cell(35, 7, "Статус", fill=True, border=1)
        pdf.cell(55, 7, "Дата/план", fill=True, border=1, ln=True)

        pdf.set_font("DejaVu", "", 9)
        for i, v in enumerate(vaccinations):
            fill = i % 2 == 0
            pdf.set_fill_color(248, 248, 248) if fill else pdf.set_fill_color(255, 255, 255)

            if v["done_date"]:
                status = "Сделано"
                date_val = v["done_date"]
                pdf.set_text_color(40, 140, 40)
            else:
                try:
                    d = datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date()
                    if d <= date.today():
                        status = "Просрочено"
                        pdf.set_text_color(200, 60, 60)
                    else:
                        status = "Предстоит"
                        pdf.set_text_color(60, 60, 180)
                except Exception:
                    status = "Предстоит"
                    pdf.set_text_color(60, 60, 180)
                date_val = v["scheduled_date"] or "—"

            name_text = v["vaccine_name"]
            if len(name_text) > 48:
                name_text = name_text[:46] + ".."

            pdf.cell(90, 6, name_text, border=1, fill=fill)
            pdf.cell(35, 6, status, border=1, fill=fill)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(55, 6, date_val, border=1, fill=fill, ln=True)
    else:
        pdf.set_font("DejaVu", "", 11)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 8, "Прививки не добавлены", ln=True)
        pdf.set_text_color(40, 40, 40)

    pdf.ln(10)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(0, 5, "Сформировано МамаБотом · Только для личного использования", align="C", ln=True)

    return bytes(pdf.output())


async def export_pdf_select_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    children = db.get_children(user_id)

    if not children:
        keyboard = [[InlineKeyboardButton("👶 Добавить ребёнка", callback_data="my_child"),
                     InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]]
        await query.edit_message_text(
            "📄 Нет детей для экспорта. Сначала добавьте ребёнка.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if len(children) == 1:
        context.user_data["pdf_child_id"] = children[0]["id"]
        await _do_export(query, context, children[0]["id"], user_id)
        return

    keyboard = []
    for ch in children:
        emoji = "👧" if ch["gender"] == "girl" else "👦"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {ch['name']}", callback_data=f"pdf_export:{ch['id']}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="my_child")])
    await query.edit_message_text(
        "📄 *Экспорт в PDF*\n\nВыберите ребёнка:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def export_pdf_for_child(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Создаю PDF...")
    child_id = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    await _do_export(query, context, child_id, user_id)


async def _do_export(query, context, child_id: int, user_id: int):
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return

    await query.edit_message_text("⏳ Создаю PDF-отчёт, подождите...")

    growth = db.get_growth_records(child_id, user_id, limit=50)
    vaccines = db.get_vaccinations(child_id, user_id)

    try:
        pdf_bytes = generate_child_pdf(ch, growth, vaccines)
        buf = io.BytesIO(pdf_bytes)
        buf.name = f"{ch['name']}_report.pdf"

        keyboard = [[InlineKeyboardButton("👶 К ребёнку", callback_data=f"child_view:{child_id}"),
                     InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]]
        await query.message.reply_document(
            document=buf,
            filename=f"{ch['name']}_report.pdf",
            caption=f"📄 Отчёт: {ch['name']}",
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
