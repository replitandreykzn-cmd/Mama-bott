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

# ── Цвета ─────────────────────────────────────────────────────────────────────
C_ACCENT       = (99, 102, 241)
C_ACCENT_LIGHT = (238, 242, 255)
C_ACCENT_MID   = (199, 210, 254)
C_GREEN        = (34, 197, 94)
C_GREEN_LIGHT  = (240, 253, 244)
C_AMBER        = (245, 158, 11)
C_AMBER_LIGHT  = (255, 251, 235)
C_AMBER_MID    = (253, 230, 138)
C_RED          = (239, 68, 68)
C_RED_LIGHT    = (254, 242, 242)
C_PINK         = (236, 72, 153)
C_PINK_LIGHT   = (253, 242, 248)
C_DARK         = (17, 24, 39)
C_MID          = (107, 114, 128)
C_LIGHT        = (249, 250, 251)
C_BORDER       = (229, 231, 235)
C_WHITE        = (255, 255, 255)


def _ensure_font():
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"Шрифт не найден: {FONT_PATH}")


def _rr(pdf, x, y, w, h, r=3, fill_color=None, border_color=None, border=False):
    """Прямоугольник с заливкой."""
    if fill_color:
        pdf.set_fill_color(*fill_color)
    if border_color:
        pdf.set_draw_color(*border_color)
    else:
        pdf.set_draw_color(*C_BORDER)
    pdf.set_line_width(0.3)
    style = "FD" if border else "F"
    pdf.rect(x, y, w, h, style)


def _section(pdf, title, icon, accent):
    """Современный заголовок секции."""
    pdf.ln(6)
    y = pdf.get_y()
    # Цветная полоска слева
    pdf.set_fill_color(*accent)
    pdf.rect(10, y, 3, 9, "F")
    # Светлый фон
    r, g, b = accent
    light_bg = (
        r + int((255 - r) * 0.90),
        g + int((255 - g) * 0.90),
        b + int((255 - b) * 0.90),
    )
    _rr(pdf, 13, y, 187, 9, r=2, fill_color=light_bg)
    pdf.set_xy(18, y + 1)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*accent)
    pdf.cell(0, 7, f"{icon}  {title}", ln=True)
    pdf.ln(3)


def _kv(pdf, label, value, lw=42):
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*C_MID)
    pdf.cell(lw, 6, label)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*C_DARK)
    pdf.cell(0, 6, value, ln=True)


def generate_child_pdf(child, growth_records, vaccinations,
                       illnesses=None, medications=None, allergies=None, contraindications=None) -> bytes:
    _ensure_font()

    pdf = FPDF()
    pdf.add_font("DejaVu", "",  FONT_PATH)
    pdf.add_font("DejaVu", "B", FONT_PATH)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(10, 10, 10)

    gender_str  = "Девочка" if child["gender"] == "girl" else "Мальчик"
    gender_icon = "♀" if child["gender"] == "girl" else "♂"
    age         = age_str(child["birthdate"])
    today_str   = date.today().strftime("%d.%m.%Y")

    # ── ШАПКА ────────────────────────────────────────────────────────────────
    pdf.set_fill_color(*C_ACCENT)
    pdf.rect(0, 0, 105, 30, "F")
    pdf.set_fill_color(*C_PINK)
    pdf.rect(105, 0, 105, 30, "F")
    pdf.set_font("DejaVu", "B", 18)
    pdf.set_text_color(*C_WHITE)
    pdf.set_xy(0, 6)
    pdf.cell(210, 10, "МамаБот", align="C", ln=True)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(225, 225, 255)
    pdf.cell(210, 6, "Медицинский отчёт для педиатра", align="C", ln=True)
    pdf.ln(5)

    # ── КАРТОЧКА РЕБЁНКА ─────────────────────────────────────────────────────
    y0 = pdf.get_y()
    _rr(pdf, 10, y0, 190, 36, r=4, fill_color=C_WHITE,
        border_color=C_BORDER, border=True)
    pdf.set_fill_color(*C_ACCENT)
    pdf.rect(10, y0, 4, 36, "F")

    pdf.set_xy(18, y0 + 5)
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(110, 9, f"{gender_icon}  {child['name']}")
    pdf.set_font("DejaVu", "", 7.5)
    pdf.set_text_color(*C_MID)
    pdf.cell(0, 9, f"Создан: {today_str}", align="R", ln=True)

    pdf.set_x(18)
    _kv(pdf, "Дата рождения:", child["birthdate"])
    pdf.set_x(18)
    _kv(pdf, "Возраст:", age)
    pdf.set_x(18)
    _kv(pdf, "Пол:", gender_str)
    pdf.set_y(y0 + 40)

    # ── РОСТ И ВЕС ───────────────────────────────────────────────────────────
    _section(pdf, "Рост и вес", "◉", C_ACCENT)

    if growth_records:
        y = pdf.get_y()
        _rr(pdf, 10, y, 190, 8, r=2, fill_color=C_ACCENT)
        pdf.set_xy(12, y + 1)
        pdf.set_font("DejaVu", "B", 9)
        pdf.set_text_color(*C_WHITE)
        pdf.cell(60, 6, "Дата")
        pdf.cell(60, 6, "Рост (см)", align="C")
        pdf.cell(60, 6, "Вес (кг)",  align="C", ln=True)

        for i, r in enumerate(growth_records):
            y = pdf.get_y()
            bg = C_ACCENT_LIGHT if i % 2 == 0 else C_WHITE
            _rr(pdf, 10, y, 190, 7, r=0, fill_color=bg)
            h = str(r["height_cm"]) if r["height_cm"] else "—"
            w = str(r["weight_kg"]) if r["weight_kg"] else "—"
            pdf.set_xy(12, y + 0.5)
            pdf.set_font("DejaVu", "", 9)
            pdf.set_text_color(*C_DARK)
            pdf.cell(60, 6, r["date"])
            pdf.set_font("DejaVu", "B", 9)
            pdf.set_text_color(*C_ACCENT)
            pdf.cell(60, 6, h, align="C")
            pdf.cell(60, 6, w, align="C", ln=True)

        last = growth_records[0]
        y = pdf.get_y() + 2
        _rr(pdf, 10, y, 190, 7, r=2, fill_color=C_ACCENT_MID)
        h_s = f"{last['height_cm']} см" if last["height_cm"] else "—"
        w_s = f"{last['weight_kg']} кг" if last["weight_kg"] else "—"
        pdf.set_xy(12, y + 1)
        pdf.set_font("DejaVu", "B", 8.5)
        pdf.set_text_color(*C_ACCENT)
        pdf.cell(0, 5, f"Последний замер: {last['date']}  ·  {h_s}  ·  {w_s}", ln=True)
    else:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*C_MID)
        pdf.cell(0, 7, "  Записей пока нет", ln=True)

    # ── ПРИВИВКИ ─────────────────────────────────────────────────────────────
    _section(pdf, "Прививки", "✦", C_GREEN)

    if vaccinations:
        done    = [v for v in vaccinations if v["done_date"]]
        pending = [v for v in vaccinations if not v["done_date"]]
        overdue = []
        for v in pending:
            if v["scheduled_date"]:
                try:
                    if datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date() <= date.today():
                        overdue.append(v)
                except Exception:
                    pass

        # Три карточки статистики
        y = pdf.get_y()
        stats = [
            (f"Сделано: {len(done)}",                    C_GREEN_LIGHT,  C_GREEN),
            (f"Просрочено: {len(overdue)}",               C_AMBER_LIGHT,  C_AMBER),
            (f"Предстоит: {len(pending)-len(overdue)}",  C_ACCENT_LIGHT, C_ACCENT),
        ]
        cw = 62
        for i, (txt, bg, fg) in enumerate(stats):
            cx = 10 + i * (cw + 2)
            _rr(pdf, cx, y, cw, 10, r=3, fill_color=bg,
                border_color=fg, border=True)
            pdf.set_xy(cx, y + 2)
            pdf.set_font("DejaVu", "B", 9)
            pdf.set_text_color(*fg)
            pdf.cell(cw, 6, txt, align="C")
        pdf.ln(14)

        y = pdf.get_y()
        _rr(pdf, 10, y, 190, 8, r=2, fill_color=C_GREEN)
        pdf.set_xy(12, y + 1)
        pdf.set_font("DejaVu", "B", 8.5)
        pdf.set_text_color(*C_WHITE)
        pdf.cell(100, 6, "Прививка")
        pdf.cell(45,  6, "Статус",     align="C")
        pdf.cell(43,  6, "Дата / план", align="C", ln=True)

        for i, v in enumerate(vaccinations):
            y = pdf.get_y()
            bg = C_GREEN_LIGHT if i % 2 == 0 else C_WHITE
            _rr(pdf, 10, y, 190, 6, r=0, fill_color=bg)
            pdf.set_xy(12, y + 0.5)

            name_text = v["vaccine_name"]
            if len(name_text) > 54:
                name_text = name_text[:52] + ".."

            if v["done_date"]:
                status, sc, dv = "✓ Сделано", C_GREEN, v["done_date"]
            else:
                try:
                    d = datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date()
                    status, sc = ("! Просрочено", C_RED) if d <= date.today() else ("→ Предстоит", C_ACCENT)
                except Exception:
                    status, sc = "→ Предстоит", C_ACCENT
                dv = v["scheduled_date"] or "—"

            pdf.set_font("DejaVu", "", 8.5)
            pdf.set_text_color(*C_DARK)
            pdf.cell(100, 5, f"  {name_text}")
            pdf.set_font("DejaVu", "B", 8.5)
            pdf.set_text_color(*sc)
            pdf.cell(45, 5, status, align="C")
            pdf.set_font("DejaVu", "", 8.5)
            pdf.set_text_color(*C_MID)
            pdf.cell(43, 5, dv, align="C", ln=True)
    else:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*C_MID)
        pdf.cell(0, 7, "  Прививки не добавлены", ln=True)

    # ── ИСТОРИЯ БОЛЕЗНЕЙ ─────────────────────────────────────────────────────
    _section(pdf, "История болезней", "♥", C_AMBER)

    if illnesses:
        for ill in illnesses:
            end_str   = ill["end_date"] or "не закрыта"
            is_active = not ill["end_date"]

            y = pdf.get_y()
            _rr(pdf, 10, y, 190, 8, r=3, fill_color=C_AMBER_LIGHT,
                border_color=C_AMBER, border=True)
            pdf.set_xy(14, y + 1.5)
            pdf.set_font("DejaVu", "B", 9)
            pdf.set_text_color(*C_DARK)
            pdf.cell(130, 5, ill["illness_name"])
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*C_MID)
            pdf.cell(0, 5, f"{ill['start_date']} — {end_str}", align="R")
            pdf.ln(9)

            if is_active:
                y2 = pdf.get_y() - 3
                _rr(pdf, 14, y2, 24, 6, r=2, fill_color=C_AMBER_MID)
                pdf.set_xy(14, y2 + 0.8)
                pdf.set_font("DejaVu", "B", 7.5)
                pdf.set_text_color(*C_AMBER)
                pdf.cell(24, 5, "● АКТИВНО", align="C", ln=True)
                pdf.ln(2)

            entries = db.get_illness_entries(ill["id"])
            if entries:
                y = pdf.get_y()
                _rr(pdf, 14, y, 184, 6, r=1, fill_color=C_AMBER)
                pdf.set_xy(16, y + 0.5)
                pdf.set_font("DejaVu", "B", 7.5)
                pdf.set_text_color(*C_WHITE)
                pdf.cell(30, 5, "Дата")
                pdf.cell(20, 5, "Темп.", align="C")
                pdf.cell(70, 5, "Симптомы")
                pdf.cell(64, 5, "Лекарства", ln=True)

                for j, e in enumerate(entries):
                    y = pdf.get_y()
                    bg2 = C_AMBER_LIGHT if j % 2 == 0 else C_WHITE
                    _rr(pdf, 14, y, 184, 6, r=0, fill_color=bg2)
                    pdf.set_xy(16, y + 0.5)
                    temp = f"{e['temperature']}°" if e["temperature"] else "—"
                    symp = (e["symptoms"] or "—")[:38]
                    meds_g = (e["medications_given"] or "—")[:36]
                    hi = e["temperature"] and float(e["temperature"]) >= 38
                    pdf.set_font("DejaVu", "", 7.5)
                    pdf.set_text_color(*C_DARK)
                    pdf.cell(30, 5, e["entry_date"])
                    pdf.set_text_color(*(C_RED if hi else C_DARK))
                    pdf.set_font("DejaVu", "B" if hi else "", 7.5)
                    pdf.cell(20, 5, temp, align="C")
                    pdf.set_font("DejaVu", "", 7.5)
                    pdf.set_text_color(*C_DARK)
                    pdf.cell(70, 5, symp)
                    pdf.set_text_color(*C_MID)
                    pdf.cell(64, 5, meds_g, ln=True)
            pdf.ln(4)
    else:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*C_MID)
        pdf.cell(0, 7, "  Болезней не записано", ln=True)

    # ── ЛЕКАРСТВА ────────────────────────────────────────────────────────────
    _section(pdf, "Лекарства", "✚", C_PINK)

    if medications:
        y = pdf.get_y()
        _rr(pdf, 10, y, 190, 8, r=2, fill_color=C_PINK)
        pdf.set_xy(12, y + 1)
        pdf.set_font("DejaVu", "B", 8.5)
        pdf.set_text_color(*C_WHITE)
        pdf.cell(65, 6, "Название")
        pdf.cell(40, 6, "Доза",     align="C")
        pdf.cell(45, 6, "Интервал", align="C")
        pdf.cell(38, 6, "До даты",  align="C", ln=True)

        for i, m in enumerate(medications):
            y = pdf.get_y()
            bg = C_PINK_LIGHT if i % 2 == 0 else C_WHITE
            _rr(pdf, 10, y, 190, 7, r=0, fill_color=bg)
            pdf.set_xy(12, y + 1)
            ih = int(m["interval_hours"])
            im = int((m["interval_hours"] - ih) * 60)
            ivl = f"каждые {ih} ч." if im == 0 else f"каждые {ih} ч. {im} мин."
            pdf.set_font("DejaVu", "B", 8.5)
            pdf.set_text_color(*C_DARK)
            pdf.cell(65, 5, (m["name"] or "")[:32])
            pdf.set_font("DejaVu", "", 8.5)
            pdf.set_text_color(*C_PINK)
            pdf.cell(40, 5, (m["dose"] or "—")[:18], align="C")
            pdf.set_text_color(*C_MID)
            pdf.cell(45, 5, ivl,                      align="C")
            pdf.cell(38, 5, m["end_date"] or "—",     align="C", ln=True)
    else:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*C_MID)
        pdf.cell(0, 7, "  Лекарства не записаны", ln=True)

    # ── АЛЛЕРГИИ И ПРОТИВОПОКАЗАНИЯ ─────────────────────────────────────────
    C_VIOLET       = (139, 92, 246)
    C_VIOLET_LIGHT = (245, 243, 255)

    _section(pdf, "Аллергии и противопоказания", "⚠", C_VIOLET)

    if allergies:
        y = pdf.get_y()
        _rr(pdf, 10, y, 190, 8, r=2, fill_color=C_VIOLET)
        pdf.set_xy(12, y + 1)
        pdf.set_font("DejaVu", "B", 8.5)
        pdf.set_text_color(*C_WHITE)
        pdf.cell(70, 6, "Аллерген")
        pdf.cell(70, 6, "Реакция",   align="C")
        pdf.cell(48, 6, "Тяжесть",   align="C", ln=True)

        sev_map = {"mild": "🟡 Лёгкая", "moderate": "🟠 Средняя", "severe": "🔴 Тяжёлая"}
        for i, a in enumerate(allergies):
            y = pdf.get_y()
            bg = C_VIOLET_LIGHT if i % 2 == 0 else C_WHITE
            _rr(pdf, 10, y, 190, 7, r=0, fill_color=bg)
            pdf.set_xy(12, y + 1)
            sev_str = sev_map.get(a["severity"], "—")
            sev_color = {"mild": C_AMBER, "moderate": (249, 115, 22), "severe": C_RED}.get(a["severity"], C_MID)
            pdf.set_font("DejaVu", "B", 8.5)
            pdf.set_text_color(*C_DARK)
            pdf.cell(70, 5, (a["name"] or "")[:36])
            pdf.set_font("DejaVu", "", 8.5)
            pdf.set_text_color(*C_MID)
            pdf.cell(70, 5, (a["reaction"] or "—")[:36], align="C")
            pdf.set_font("DejaVu", "B", 8.5)
            pdf.set_text_color(*sev_color)
            pdf.cell(48, 5, sev_str, align="C", ln=True)
    else:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*C_MID)
        pdf.cell(0, 7, "  Аллергий не записано", ln=True)

    if contraindications:
        pdf.ln(3)
        pdf.set_font("DejaVu", "B", 9)
        pdf.set_text_color(*C_VIOLET)
        pdf.set_x(12)
        pdf.cell(0, 6, "🚫  Противопоказания:", ln=True)
        for c in contraindications:
            pdf.set_x(14)
            pdf.set_font("DejaVu", "", 8.5)
            pdf.set_text_color(*C_DARK)
            pdf.cell(0, 5, f"• {c['name']}", ln=True)

    # ── ПОДВАЛ ───────────────────────────────────────────────────────────────
    pdf.ln(8)
    y = pdf.get_y()
    _rr(pdf, 10, y, 190, 10, r=3, fill_color=C_LIGHT)
    pdf.set_xy(10, y + 2)
    pdf.set_font("DejaVu", "", 7.5)
    pdf.set_text_color(*C_MID)
    pdf.cell(0, 6,
             "МамаБот  ·  Отчёт сформирован автоматически  ·  Только для личного использования",
             align="C", ln=True)

    return bytes(pdf.output())


# ── Telegram handlers ─────────────────────────────────────────────────────────

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
    growth      = db.get_growth_records(child_id, user_id, limit=100)
    vaccines    = db.get_vaccinations(child_id, user_id)
    illnesses   = db.get_illnesses(child_id, active_only=False, limit=20)
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
    growth      = db.get_growth_records(child_id, user_id, limit=100)
    vaccines    = db.get_vaccinations(child_id, user_id)
    illnesses   = db.get_illnesses(child_id, active_only=False, limit=20)
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
