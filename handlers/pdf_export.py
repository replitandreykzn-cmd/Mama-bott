def generate_child_pdf(child, growth_records, vaccinations, illnesses=None, medications=None) -> bytes:
    _ensure_font()

    pdf = FPDF()

    pdf.add_font("DejaVu", "", FONT_PATH)
    pdf.add_font("DejaVu", "B", FONT_PATH)

    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(10, 10, 10)

    # ФОН
    pdf.set_fill_color(*C_BG)
    pdf.rect(0, 0, 210, 297, "F")

    gender_str = "Девочка" if child["gender"] == "girl" else "Мальчик"
    gender_icon = "👧" if child["gender"] == "girl" else "👦"
    age = age_str(child["birthdate"])

    # ── HEADER ─────────────────────────────────────
    pdf.set_fill_color(*C_PRIMARY)
    pdf.rect(0, 0, 210, 34, "F")

    pdf.set_xy(12, 9)
    pdf.set_font("DejaVu", "B", 22)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "МамаБот")

    pdf.set_xy(12, 20)
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 5, "Медицинский отчёт для педиатра")

    pdf.set_xy(150, 12)
    pdf.set_font("DejaVu", "", 9)
    pdf.cell(40, 5, date.today().strftime('%d.%m.%Y'), align="R")

    pdf.ln(32)

    # ── CHILD CARD ─────────────────────────────────
    y = pdf.get_y()
    card(pdf, y, 38)

    pdf.set_xy(16, y + 6)
    pdf.set_font("DejaVu", "B", 18)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(0, 8, f"{gender_icon} {child['name']}")

    pdf.set_xy(16, y + 18)
    pdf.set_font("DejaVu", "", 10)

    muted(pdf)
    pdf.cell(42, 6, "Дата рождения:")
    normal(pdf)
    pdf.cell(45, 6, child["birthdate"])

    muted(pdf)
    pdf.cell(22, 6, "Возраст:")

    pdf.set_text_color(*C_PRIMARY)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(35, 6, age)

    pdf.set_font("DejaVu", "", 10)
    muted(pdf)
    pdf.cell(14, 6, "Пол:")

    normal(pdf)
    pdf.cell(0, 6, gender_str)

    pdf.set_y(y + 45)

    # ── SUMMARY ────────────────────────────────────
    section_title(pdf, "Сводка")

    active_illnesses = len([x for x in illnesses or [] if not x["end_date"]])
    overdue = 0

    for v in vaccinations or []:
        if not v["done_date"] and v["scheduled_date"]:
            try:
                if datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date() <= date.today():
                    overdue += 1
            except Exception:
                pass

    last_growth = growth_records[0] if growth_records else None

    y = pdf.get_y()

    # BLOCK 1
    pdf.set_fill_color(*C_PRIMARY_LIGHT)
    pdf.rect(10, y, 60, 22, "F")

    pdf.set_xy(14, y + 4)
    pdf.set_font("DejaVu", "", 9)
    muted(pdf)
    pdf.cell(0, 5, "Последний вес")

    pdf.set_xy(14, y + 11)
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*C_PRIMARY)

    if last_growth and last_growth["weight_kg"]:
        pdf.cell(0, 6, f"{last_growth['weight_kg']} кг")
    else:
        pdf.cell(0, 6, "—")

    # BLOCK 2
    pdf.set_fill_color(*C_WARNING_BG)
    pdf.rect(75, y, 60, 22, "F")

    pdf.set_xy(79, y + 4)
    pdf.set_font("DejaVu", "", 9)
    muted(pdf)
    pdf.cell(0, 5, "Просрочено прививок")

    pdf.set_xy(79, y + 11)
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*C_WARNING)
    pdf.cell(0, 6, str(overdue))

    # BLOCK 3
    pdf.set_fill_color(*C_DANGER_BG)
    pdf.rect(140, y, 60, 22, "F")

    pdf.set_xy(144, y + 4)
    pdf.set_font("DejaVu", "", 9)
    muted(pdf)
    pdf.cell(0, 5, "Активные болезни")

    pdf.set_xy(144, y + 11)
    pdf.set_font("DejaVu", "B", 15)
    pdf.set_text_color(*C_DANGER)
    pdf.cell(0, 6, str(active_illnesses))

    pdf.ln(30)

    # ── GROWTH ─────────────────────────────────────
    section_title(pdf, "Рост и вес")

    if growth_records:
        pdf.set_fill_color(*C_PRIMARY)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("DejaVu", "B", 10)

        pdf.cell(70, 10, "Дата", fill=True)
        pdf.cell(55, 10, "Рост", fill=True, align="C")
        pdf.cell(55, 10, "Вес", fill=True, align="C", ln=True)

        for i, r in enumerate(growth_records):
            bg = (255, 255, 255) if i % 2 == 0 else (245, 247, 252)

            pdf.set_fill_color(*bg)
            pdf.set_text_color(*C_TEXT)
            pdf.set_font("DejaVu", "", 10)

            pdf.cell(70, 9, r["date"], fill=True)
            pdf.cell(55, 9, f"{r['height_cm'] or '—'} см", fill=True, align="C")
            pdf.cell(55, 9, f"{r['weight_kg'] or '—'} кг", fill=True, align="C", ln=True)

    else:
        muted(pdf)
        pdf.cell(0, 8, "Нет записей", ln=True)

    # ── VACCINES ───────────────────────────────────
    section_title(pdf, "Прививки")

    if vaccinations:
        for v in vaccinations:
            y = pdf.get_y()

            is_done = bool(v["done_date"])

            if is_done:
                bg = C_SUCCESS_BG
                color = C_SUCCESS
                status = "Сделано"
                date_text = v["done_date"]
            else:
                bg = C_WARNING_BG
                color = C_WARNING
                status = "Ожидается"
                date_text = v["scheduled_date"] or "—"

            pdf.set_fill_color(*bg)
            pdf.rect(10, y, 190, 16, "F")

            pdf.set_xy(14, y + 3)
            pdf.set_font("DejaVu", "B", 10)
            pdf.set_text_color(*C_TEXT)
            pdf.cell(110, 5, v["vaccine_name"])

            pdf.set_xy(14, y + 9)
            pdf.set_font("DejaVu", "", 8)
            muted(pdf)
            pdf.cell(0, 4, date_text)

            pdf.set_xy(145, y + 5)
            pdf.set_font("DejaVu", "B", 9)
            pdf.set_text_color(*color)
            pdf.cell(45, 5, status, align="R")

            pdf.ln(18)

    else:
        muted(pdf)
        pdf.cell(0, 8, "Прививки не добавлены", ln=True)

    # ── ILLNESSES ──────────────────────────────────
    section_title(pdf, "История болезней")

    if illnesses:
        for ill in illnesses:
            y = pdf.get_y()

            active = not ill["end_date"]

            bg = C_DANGER_BG if active else (245, 245, 245)
            color = C_DANGER if active else C_TEXT

            pdf.set_fill_color(*bg)
            pdf.rect(10, y, 190, 18, "F")

            pdf.set_xy(14, y + 4)
            pdf.set_font("DejaVu", "B", 11)
            pdf.set_text_color(*color)
            pdf.cell(0, 5, ill["illness_name"])

            pdf.set_xy(14, y + 10)
            pdf.set_font("DejaVu", "", 8)
            muted(pdf)

            end = ill["end_date"] or "активно"
            pdf.cell(0, 4, f"{ill['start_date']} — {end}")

            pdf.ln(22)

            entries = db.get_illness_entries(ill["id"])

            for e in entries[:5]:
                pdf.set_font("DejaVu", "", 8)
                normal(pdf)

                temp = f" | {e['temperature']}°" if e["temperature"] else ""
                symp = e["symptoms"] or ""

                pdf.multi_cell(
                    190,
                    5,
                    f"• {e['entry_date']}{temp}\n{symp}",
                    border=0
                )

                pdf.ln(2)

    else:
        muted(pdf)
        pdf.cell(0, 8, "Болезни не записаны", ln=True)

    # ── MEDICATIONS ────────────────────────────────
    section_title(pdf, "Лекарства")

    if medications:
        for m in medications:
            y = pdf.get_y()

            pdf.set_fill_color(*C_PURPLE_BG)
            pdf.rect(10, y, 190, 16, "F")

            pdf.set_xy(14, y + 3)
            pdf.set_font("DejaVu", "B", 10)
            pdf.set_text_color(*C_TEXT)
            pdf.cell(90, 5, m["name"] or "—")

            pdf.set_xy(14, y + 9)
            pdf.set_font("DejaVu", "", 8)
            muted(pdf)

            interval = f"каждые {m['interval_hours']}ч"
            end_date = m["end_date"] or "—"

            pdf.cell(0, 4, f"{m['dose']} · {interval} · до {end_date}")

            pdf.ln(18)

    else:
        muted(pdf)
        pdf.cell(0, 8, "Лекарства не добавлены", ln=True)

    # ── FOOTER ─────────────────────────────────────
    pdf.ln(8)

    pdf.set_draw_color(*C_BORDER)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())

    pdf.ln(5)

    pdf.set_font("DejaVu", "", 8)
    muted(pdf)

    pdf.cell(
        0,
        5,
        "МамаБот · Отчёт сформирован автоматически · Только для личного использования",
        align="C"
    )

    return bytes(pdf.output())
