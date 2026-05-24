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


# ─────────────────────────────────────────────────────────────
# PDF DESIGN
# ─────────────────────────────────────────────────────────────

PRIMARY = (103, 80, 164)
PRIMARY_LIGHT = (237, 231, 246)

GREEN = (76, 175, 80)
GREEN_LIGHT = (232, 245, 233)

RED = (229, 57, 53)
RED_LIGHT = (255, 235, 238)

BLUE = (33, 150, 243)
BLUE_LIGHT = (227, 242, 253)

ORANGE = (251, 140, 0)
ORANGE_LIGHT = (255, 243, 224)

GRAY = (120, 120, 120)
TEXT = (40, 40, 40)


# ─────────────────────────────────────────────────────────────
# PDF CLASS
# ─────────────────────────────────────────────────────────────

class BeautifulPDF(FPDF):

    def header(self):
        if self.page_no() == 1:
            return

        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, 210, 18, "F")

        self.set_text_color(255, 255, 255)
        self.set_font("DejaVu", "B", 12)

        self.set_xy(12, 5)
        self.cell(0, 6, "МамаБот — Медицинская карта ребёнка")

        self.ln(15)

    def footer(self):
        self.set_y(-15)

        self.set_draw_color(220, 220, 220)
        self.line(10, self.get_y(), 200, self.get_y())

        self.set_text_color(150, 150, 150)
        self.set_font("DejaVu", "", 9)

        self.cell(
            0,
            10,
            f"Страница {self.page_no()}",
            align="C"
        )


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _ensure_font():
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(
            f"Шрифт не найден: {FONT_PATH}"
        )


def section_title(pdf, title, color, light):
    pdf.ln(4)

    pdf.set_fill_color(*light)
    pdf.rounded_rect(10, pdf.get_y(), 190, 10, 2, style="F")

    pdf.set_xy(14, pdf.get_y() + 2)

    pdf.set_font("DejaVu", "B", 14)
    pdf.set_text_color(*color)

    pdf.cell(0, 6, title)

    pdf.ln(12)


def info_card(pdf, label, value):
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(45, 8, label)

    pdf.set_font("DejaVu", "", 11)
    pdf.set_text_color(*TEXT)
    pdf.multi_cell(0, 8, value)


def draw_summary_box(pdf, title, value, color, light):
    x = pdf.get_x()
    y = pdf.get_y()

    pdf.set_fill_color(*light)
    pdf.rounded_rect(x, y, 58, 24, 3, style="F")

    pdf.set_xy(x, y + 4)

    pdf.set_text_color(*color)
    pdf.set_font("DejaVu", "B", 18)
    pdf.cell(58, 8, str(value), align="C")

    pdf.set_xy(x, y + 14)

    pdf.set_font("DejaVu", "", 10)
    pdf.cell(58, 5, title, align="C")

    pdf.set_xy(x + 63, y)


def status_chip(pdf, text, status):
    if status == "done":
        bg = GREEN_LIGHT
        fg = GREEN
    elif status == "overdue":
        bg = RED_LIGHT
        fg = RED
    else:
        bg = BLUE_LIGHT
        fg = BLUE

    pdf.set_fill_color(*bg)
    pdf.set_text_color(*fg)

    x = pdf.get_x()
    y = pdf.get_y()

    pdf.rounded_rect(x, y, 34, 7, 2, style="F")

    pdf.set_xy(x, y + 1.3)

    pdf.set_font("DejaVu", "B", 9)
    pdf.cell(34, 4, text, align="C")


# ─────────────────────────────────────────────────────────────
# MAIN PDF GENERATOR
# ─────────────────────────────────────────────────────────────

def generate_child_pdf(
        child,
        growth_records,
        vaccinations,
        illnesses=None,
        medications=None
) -> bytes:

    _ensure_font()

    pdf = BeautifulPDF()
    pdf.add_font("DejaVu", "", FONT_PATH)
    pdf.add_font("DejaVu", "B", FONT_PATH)

    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ───────────────── TITLE PAGE ─────────────────

    pdf.set_fill_color(*PRIMARY)
    pdf.rect(0, 0, 210, 297, "F")

    pdf.set_text_color(255, 255, 255)

    pdf.set_font("DejaVu", "B", 30)
    pdf.ln(55)
    pdf.cell(0, 15, "МЕДИЦИНСКАЯ", align="C", ln=True)
    pdf.cell(0, 15, "КАРТА РЕБЁНКА", align="C", ln=True)

    pdf.ln(20)

    pdf.set_font("DejaVu", "", 16)

    gender_emoji = "👧" if child["gender"] == "girl" else "👦"

    pdf.cell(
        0,
        10,
        f"{gender_emoji} {child['name']}",
        align="C",
        ln=True
    )

    pdf.set_font("DejaVu", "", 12)

    pdf.cell(
        0,
        8,
        f"Дата создания: {date.today().strftime('%d.%m.%Y')}",
        align="C",
        ln=True
    )

    pdf.cell(
        0,
        8,
        f"Возраст: {age_str(child['birthdate'])}",
        align="C",
        ln=True
    )

    pdf.ln(40)

    pdf.set_font("DejaVu", "", 11)

    text = (
        "Этот отчёт создан автоматически в МамаБоте.\n\n"
        "Документ содержит историю роста, прививок, "
        "болезней, лекарств и другую важную информацию "
        "для педиатра."
    )

    pdf.multi_cell(
        160,
        8,
        text,
        align="C"
    )

    # ───────────────── PAGE 2 ─────────────────

    pdf.add_page()

    # PROFILE

    section_title(
        pdf,
        "👶 Информация о ребёнке",
        PRIMARY,
        PRIMARY_LIGHT
    )

    gender = (
        "Девочка"
        if child["gender"] == "girl"
        else "Мальчик"
    )

    info_card(pdf, "Имя:", child["name"])
    info_card(pdf, "Дата рождения:", child["birthdate"])
    info_card(pdf, "Возраст:", age_str(child["birthdate"]))
    info_card(pdf, "Пол:", gender)

    # SUMMARY

    section_title(
        pdf,
        "📊 Краткая сводка",
        BLUE,
        BLUE_LIGHT
    )

    done_vaccines = [
        v for v in vaccinations
        if v["done_date"]
    ]

    pending_vaccines = [
        v for v in vaccinations
        if not v["done_date"]
    ]

    active_illnesses = [
        i for i in (illnesses or [])
        if i.get("is_active")
    ]

    active_meds = medications or []

    draw_summary_box(
        pdf,
        "Прививки",
        len(done_vaccines),
        GREEN,
        GREEN_LIGHT
    )

    draw_summary_box(
        pdf,
        "Предстоит",
        len(pending_vaccines),
        BLUE,
        BLUE_LIGHT
    )

    draw_summary_box(
        pdf,
        "Болезни",
        len(active_illnesses),
        RED,
        RED_LIGHT
    )

    pdf.ln(32)

    draw_summary_box(
        pdf,
        "Лекарства",
        len(active_meds),
        ORANGE,
        ORANGE_LIGHT
    )

    draw_summary_box(
        pdf,
        "Рост/вес",
        len(growth_records),
        PRIMARY,
        PRIMARY_LIGHT
    )

    # ───────────────── GROWTH ─────────────────

    section_title(
        pdf,
        "📏 Рост и вес",
        BLUE,
        BLUE_LIGHT
    )

    if growth_records:

        pdf.set_fill_color(240, 240, 255)

        pdf.set_font("DejaVu", "B", 10)

        pdf.cell(50, 9, "Дата", border=0, fill=True)
        pdf.cell(60, 9, "Рост", border=0, fill=True)
        pdf.cell(60, 9, "Вес", border=0, fill=True, ln=True)

        pdf.set_font("DejaVu", "", 10)

        for i, r in enumerate(growth_records):

            fill = i % 2 == 0

            if fill:
                pdf.set_fill_color(248, 248, 255)
            else:
                pdf.set_fill_color(255, 255, 255)

            pdf.cell(
                50,
                9,
                str(r["date"]),
                fill=True
            )

            h = (
                f"{r['height_cm']} см"
                if r["height_cm"]
                else "—"
            )

            w = (
                f"{r['weight_kg']} кг"
                if r["weight_kg"]
                else "—"
            )

            pdf.cell(60, 9, h, fill=True)
            pdf.cell(60, 9, w, fill=True, ln=True)

    else:
        pdf.set_text_color(*GRAY)
        pdf.multi_cell(
            0,
            8,
            "Записи роста и веса отсутствуют."
        )

    # ───────────────── VACCINES ─────────────────

    pdf.add_page()

    section_title(
        pdf,
        "💉 Прививки",
        GREEN,
        GREEN_LIGHT
    )

    if vaccinations:

        for v in vaccinations:

            pdf.set_fill_color(250, 250, 250)

            start_y = pdf.get_y()

            pdf.rounded_rect(
                10,
                start_y,
                190,
                20,
                2,
                style="F"
            )

            pdf.set_xy(14, start_y + 3)

            pdf.set_font("DejaVu", "B", 11)
            pdf.set_text_color(*TEXT)

            pdf.cell(
                110,
                6,
                v["vaccine_name"]
            )

            if v["done_date"]:
                status_chip(pdf, "Сделано", "done")
            else:
                try:
                    d = datetime.strptime(
                        v["scheduled_date"],
                        "%d.%m.%Y"
                    ).date()

                    if d <= date.today():
                        status_chip(
                            pdf,
                            "Просрочено",
                            "overdue"
                        )
                    else:
                        status_chip(
                            pdf,
                            "Предстоит",
                            "pending"
                        )
                except Exception:
                    status_chip(
                        pdf,
                        "Предстоит",
                        "pending"
                    )

            pdf.set_xy(14, start_y + 11)

            pdf.set_font("DejaVu", "", 10)
            pdf.set_text_color(100, 100, 100)

            dtext = (
                v["done_date"]
                if v["done_date"]
                else v["scheduled_date"] or "—"
            )

            pdf.cell(
                0,
                5,
                f"Дата: {dtext}"
            )

            pdf.ln(24)

    else:
        pdf.set_text_color(*GRAY)
        pdf.multi_cell(
            0,
            8,
            "Прививки отсутствуют."
        )

    # ───────────────── ILLNESSES ─────────────────

    if illnesses:

        pdf.add_page()

        section_title(
            pdf,
            "🤒 История болезней",
            RED,
            RED_LIGHT
        )

        for ill in illnesses:

            start = ill["start_date"]
            end = ill["end_date"] or "не закрыта"

            pdf.set_fill_color(255, 250, 250)

            y = pdf.get_y()

            pdf.rounded_rect(
                10,
                y,
                190,
                18,
                2,
                style="F"
            )

            pdf.set_xy(14, y + 3)

            pdf.set_font("DejaVu", "B", 12)
            pdf.set_text_color(*RED)

            pdf.cell(
                0,
                6,
                ill["illness_name"]
            )

            pdf.set_xy(14, y + 10)

            pdf.set_font("DejaVu", "", 10)
            pdf.set_text_color(*TEXT)

            pdf.cell(
                0,
                5,
                f"Период: {start} — {end}"
            )

            pdf.ln(24)

            entries = db.get_illness_entries(ill["id"])

            for e in entries:

                txt = []

                if e["temperature"]:
                    txt.append(
                        f"🌡 Температура: {e['temperature']}°"
                    )

                if e["symptoms"]:
                    txt.append(
                        f"😷 Симптомы: {e['symptoms']}"
                    )

                if e["medications_given"]:
                    txt.append(
                        f"💊 Лекарства: {e['medications_given']}"
                    )

                if e["notes"]:
                    txt.append(
                        f"📝 Заметки: {e['notes']}"
                    )

                pdf.set_fill_color(252, 252, 252)

                y2 = pdf.get_y()

                height = 10 + len(txt) * 6

                pdf.rounded_rect(
                    14,
                    y2,
                    182,
                    height,
                    2,
                    style="F"
                )

                pdf.set_xy(18, y2 + 3)

                pdf.set_font("DejaVu", "B", 10)

                pdf.cell(
                    0,
                    5,
                    f"📅 {e['entry_date']}",
                    ln=True
                )

                pdf.set_x(18)

                pdf.set_font("DejaVu", "", 10)

                for t in txt:
                    pdf.multi_cell(
                        170,
                        5,
                        t
                    )

                pdf.ln(4)

    # ───────────────── MEDICATIONS ─────────────────

    if medications:

        pdf.add_page()

        section_title(
            pdf,
            "💊 Активные лекарства",
            ORANGE,
            ORANGE_LIGHT
        )

        for m in medications:

            pdf.set_fill_color(255, 248, 240)

            y = pdf.get_y()

            pdf.rounded_rect(
                10,
                y,
                190,
                20,
                2,
                style="F"
            )

            pdf.set_xy(14, y + 3)

            pdf.set_font("DejaVu", "B", 11)
            pdf.set_text_color(*ORANGE)

            pdf.cell(
                0,
                6,
                m["name"]
            )

            pdf.set_xy(14, y + 10)

            pdf.set_font("DejaVu", "", 10)
            pdf.set_text_color(*TEXT)

            dose = m["dose"] or "не указана"

            interval = (
                f"каждые {m['interval_hours']} ч."
            )

            end_date = (
                m["end_date"]
                or "без ограничения"
            )

            pdf.multi_cell(
                0,
                5,
                f"Дозировка: {dose}\n"
                f"Интервал: {interval}\n"
                f"До: {end_date}"
            )

            pdf.ln(8)

    # ───────────────── DOCTOR SUMMARY ─────────────────

    pdf.add_page()

    section_title(
        pdf,
        "🩺 Сводка для педиатра",
        PRIMARY,
        PRIMARY_LIGHT
    )

    latest_growth = (
        growth_records[0]
        if growth_records
        else None
    )

    latest_ill = (
        illnesses[0]
        if illnesses
        else None
    )

    summary = []

    summary.append(
        f"Возраст ребёнка: {age_str(child['birthdate'])}"
    )

    summary.append(
        f"Сделано прививок: {len(done_vaccines)}"
    )

    summary.append(
        f"Предстоящих прививок: {len(pending_vaccines)}"
    )

    if latest_growth:

        if latest_growth["height_cm"]:
            summary.append(
                f"Последний рост: "
                f"{latest_growth['height_cm']} см"
            )

        if latest_growth["weight_kg"]:
            summary.append(
                f"Последний вес: "
                f"{latest_growth['weight_kg']} кг"
            )

    if latest_ill:
        summary.append(
            f"Последняя болезнь: "
            f"{latest_ill['illness_name']}"
        )

    if medications:
        meds = ", ".join(
            [m["name"] for m in medications[:5]]
        )

        summary.append(
            f"Активные лекарства: {meds}"
        )

    pdf.set_font("DejaVu", "", 12)
    pdf.set_text_color(*TEXT)

    for s in summary:

        pdf.set_fill_color(248, 248, 255)

        y = pdf.get_y()

        pdf.rounded_rect(
            10,
            y,
            190,
            12,
            2,
            style="F"
        )

        pdf.set_xy(15, y + 3)

        pdf.cell(
            0,
            5,
            s
        )

        pdf.ln(14)

    pdf.ln(10)

    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(120, 120, 120)

    pdf.multi_cell(
        0,
        6,
        "Документ создан автоматически в МамаБоте "
        "и предназначен для удобной передачи "
        "информации педиатру."
    )

    return bytes(pdf.output(dest="S"))
