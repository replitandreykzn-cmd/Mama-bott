import io
import os
import logging
from datetime import date, datetime
from fpdf import FPDF
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db

logger = logging.getLogger(__name__)

# Умный поиск файла шрифта DejaVuSans.ttf на сервере Railway
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSSIBLE_PATHS = [
    os.path.join(BASE_DIR, "DejaVuSans.ttf"),
    os.path.join(BASE_DIR, "..", "DejaVuSans.ttf"),
    os.path.join(BASE_DIR, "fonts", "DejaVuSans.ttf"),
    os.path.join(BASE_DIR, "..", "fonts", "DejaVuSans.ttf"),
]

FONT_PATH = None
for path in POSSIBLE_PATHS:
    if os.path.exists(path):
        FONT_PATH = path
        break

if not FONT_PATH:
    logger.error("КРИТИЧЕСКАЯ ОШИБКА: Файл шрифта DejaVuSans.ttf не найден!")

# ── Локальная функция расчета возраста (чтобы избежать кругового импорта) ────
def _get_age_string(birthdate_str: str) -> str:
    try:
        bd = datetime.strptime(birthdate_str, "%d.%m.%Y").date()
    except Exception:
        try:
            bd = date.fromisoformat(birthdate_str)
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
    years = months // 12
    rem = months % 12
    if rem == 0:
        return f"{years} лет"
    return f"{years} л. {rem} мес."

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
C_MUTED        = (107, 114, 128)
C_LIGHT        = (249, 250, 251)
C_WHITE        = (255, 255, 255)


class MedicalPDF(FPDF):
    def __init__(self):
        super().__init__()
        if FONT_PATH and os.path.exists(FONT_PATH):
            self.add_font("DejaVu", "", FONT_PATH, uni=True)
            self.add_font("DejaVuB", "", FONT_PATH, uni=True)
        else:
            self.add_font("Helvetica", "", "")
    
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("DejaVu" if FONT_PATH else "Helvetica", "", 8)
        self.set_text_color(*C_MUTED)
        self.cell(0, 10, "Медицинская карта ребёнка — Полный отчёт", 0, 0, "L")
        self.cell(0, 10, f"Страница {self.page_no()}", 0, 1, "R")
        self.set_draw_color(*C_ACCENT_MID)
        self.line(10, 18, 200, 18)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu" if FONT_PATH else "Helvetica", "", 8)
        self.set_text_color(*C_MUTED)
        self.cell(0, 10, f"Сгенерировано автоматически помощником МамаБот — {date.today().strftime('%d.%m.%Y')}", 0, 0, "C")


def generate_child_pdf(child, growth_records, vaccinations, illnesses, medications, medical_info=None, allergies=None, contraindications=None) -> bytes:
    pdf = MedicalPDF()
    font_main = "DejaVu" if FONT_PATH else "Helvetica"
    
    pdf.add_page()
    
    # ── ТИТУЛЬНЫЙ БЛОК ────────────────────────────────────────────────────────
    pdf.set_fill_color(*C_ACCENT_LIGHT)
    pdf.rect(10, 10, 190, 45, "F")
    
    pdf.set_xy(15, 15)
    pdf.set_font(font_main, "", 22)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(0, 10, child["name"].upper(), 0, 1)
    
    pdf.set_font(font_main, "", 11)
    pdf.set_text_color(*C_DARK)
    pdf.set_x(15)
    gender_txt = "Девочка" if child["gender"] == "girl" else "Мальчик"
    pdf.cell(0, 6, f"Пол: {gender_txt}   |   Дата рождения: {child['birthdate']} ({_get_age_string(child['birthdate'])})", 0, 1)
    
    if medical_info:
        bg = medical_info.get("blood_group", "—")
        rh = medical_info.get("blood_rh", "—")
        pol = medical_info.get("policy_number", "—")
        pdf.set_x(15)
        pdf.cell(0, 6, f"Группа крови: {bg} ({rh})   |   Полис ОМС: {pol}", 0, 1)

    pdf.set_xy(10, 60)
    
    # ── АЛЛЕРГИИ И ПРОТИВОПОКАЗАНИЯ ───────────────────────────────────────────
    if allergies or contraindications:
        pdf.set_font(font_main, "", 14)
        pdf.set_text_color(*C_RED)
        pdf.cell(0, 8, "⚠️ Важная медицинская информация", 0, 1)
        pdf.ln(2)
        
        pdf.set_font(font_main, "", 10)
        pdf.set_text_color(*C_DARK)
        if allergies:
            text_all = "Аллергии: " + ", ".join([f"{a['name']} ({a['severity']})" for a in allergies])
            pdf.multi_cell(0, 5, text_all)
        if contraindications:
            text_con = "Противопоказания: " + ", ".join([c["name"] for c in contraindications])
            pdf.multi_cell(0, 5, text_con)
        pdf.ln(5)

    # ── БЛОК 1: РОСТ И ВЕС ────────────────────────────────────────────────────
    pdf.set_font(font_main, "", 14)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(0, 8, "📏 История физического развития (Рост / Вес)", 0, 1)
    pdf.ln(2)
    
    if not growth_records:
        pdf.set_font(font_main, "", 10)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(0, 6, "Данные отсутствуют.", 0, 1)
    else:
        pdf.set_fill_color(*C_LIGHT)
        pdf.set_font(font_main, "", 10)
        pdf.set_text_color(*C_DARK)
        
        pdf.cell(50, 7, "Дата измерения", 1, 0, "C", True)
        pdf.cell(70, 7, "Рост (см)", 1, 0, "C", True)
        pdf.cell(70, 7, "Вес (кг)", 1, 1, "C", True)
        
        for g in growth_records[:15]:
            pdf.cell(50, 6, g["rec_date"], 1, 0, "C")
            pdf.cell(70, 6, str(g["height"]) if g["height"] else "—", 1, 0, "C")
            pdf.cell(70, 6, str(g["weight"]) if g["weight"] else "—", 1, 1, "C")
    pdf.ln(8)

    # ── БЛОК 2: ЖУРНАЛ БОЛЕЗНЕЙ ────────────────────────────────────────────────
    pdf.set_font(font_main, "", 14)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(0, 8, "🤒 Журнал перенесенных заболеваний", 0, 1)
    pdf.ln(2)
    
    if not illnesses:
        pdf.set_font(font_main, "", 10)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(0, 6, "Данные отсутствуют.", 0, 1)
    else:
        for ill in illnesses[:10]:
            status_txt = "[Пройдено]" if not ill["is_active"] else "[Болеет сейчас]"
            date_end = ill["end_date"] if ill["end_date"] else "по настоящее время"
            
            pdf.set_fill_color(*C_LIGHT)
            pdf.set_font(font_main, "", 11)
            pdf.set_text_color(*C_DARK)
            pdf.cell(0, 7, f"• {ill['illness_name']} ({ill['start_date']} — {date_end})  {status_txt}", 0, 1, "L", True)
            
            pdf.set_font(font_main, "", 9)
            pdf.set_text_color(*C_MUTED)
            if ill["temperature"]:
                pdf.cell(0, 5, f"   Макс. температура: {ill['temperature']} °C", 0, 1)
            if ill["symptoms"]:
                pdf.multi_cell(0, 5, f"   Симптомы: {ill['symptoms']}")
            if ill["medications"]:
                pdf.multi_cell(0, 5, f"   Лечение / Препараты: {ill['medications']}")
            pdf.ln(2)
    pdf.ln(5)

    # ── БЛОК 3: ВАКЦИНАЦИЯ ────────────────────────────────────────────────────
    if pdf.get_y() > 220:
        pdf.add_page()
        
    pdf.set_font(font_main, "", 14)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(0, 8, "💉 Календарь выполненных прививок", 0, 1)
    pdf.ln(2)
    
    done_vacs = [v for v in vaccinations if v["done_date"]]
    if not done_vacs:
        pdf.set_font(font_main, "", 10)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(0, 6, "Пока нет отметок о сделанных прививках.", 0, 1)
    else:
        pdf.set_fill_color(*C_GREEN_LIGHT)
        pdf.set_font(font_main, "", 10)
        pdf.set_text_color(*C_DARK)
        
        pdf.cell(100, 7, "Название вакцины / инфекция", 1, 0, "L", True)
        pdf.cell(45, 7, "Плановая дата", 1, 0, "C", True)
        pdf.cell(45, 7, "Дата инъекции", 1, 1, "C", True)
        
        for v in done_vacs:
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.cell(100, 6, v["vaccine_name"], 1, 0, "L")
            pdf.cell(45, 6, v["scheduled_date"] or "—", 1, 0, "C")
            pdf.cell(45, 6, v["done_date"], 1, 1, "C")
            
    return pdf.output(dest="S").encode("latin1")


async def export_to_pdf_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not FONT_PATH:
        await query.edit_message_text(
            "🛑 Ошибка экспорта: На сервере отсутствует шрифт `DejaVuSans.ttf`."
        )
        return

    parts = query.data.split(":")
    child_id = int(parts[1])
    user_id = update.effective_user.id
    await _do_export(query, context, child_id, user_id)


async def _do_export(query, context, child_id: int, user_id: int):
    ch = db.get_child(child_id, user_id)
    if not ch:
        await query.edit_message_text("Ребёнок не найден.")
        return

    await query.edit_message_text("⏳ Создаю полный PDF-отчёт для педиатра, подождите...")
    
    growth            = db.get_growth_records(child_id, user_id, limit=100)
    vaccines          = db.get_vaccinations(child_id, user_id)
    illnesses         = db.get_illnesses(child_id, active_only=False, limit=20)
    medications       = db.get_medications(child_id, active_only=False)
    medical_info      = db.get_medical_info(child_id)
    allergies         = db.get_allergies(child_id)
    contraindications = db.get_contraindications(child_id)

    try:
        pdf_bytes = generate_child_pdf(ch, growth, vaccines, illnesses, medications, medical_info, allergies, contraindications)
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
        logger.error(f"Ошибка создания PDF: {e}")
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"child_view:{child_id}")]]
        await query.message.reply_text(f"❌ Ошибка создания PDF: {e}", reply_markup=InlineKeyboardMarkup(keyboard))
