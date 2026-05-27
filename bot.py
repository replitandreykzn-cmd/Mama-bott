import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
from handlers.child import (
    show_children_menu, show_child_detail,
    start_add_child, got_child_name, got_child_date, got_child_gender,
    confirm_delete_child, do_delete_child, cancel_add,
    CHILD_NAME, CHILD_DATE, CHILD_GENDER,
)
from handlers.growth import (
    show_growth_menu, start_add_growth,
    got_growth_height, got_growth_weight, got_growth_date, cancel_growth,
    GROWTH_HEIGHT, GROWTH_WEIGHT, GROWTH_DATE,
)
from handlers.vaccines import (
    show_vaccines_menu, show_vaccines_list, show_done_list, mark_vaccine_done,
)
from handlers.reminders import (
    show_reminders_menu, start_add_reminder,
    got_reminder_title, got_reminder_date, got_reminder_time,
    show_delete_list, do_delete_reminder, cancel_reminder,
    REM_TITLE, REM_DATE, REM_TIME,
)
from handlers.subscription import (
    show_subscription_menu, activate_trial, buy_premium,
    show_family_menu, start_add_family, got_family_member_id,
    remove_family_member, cancel_family,
    FAMILY_ADD_ID,
)
from handlers.pdf_export import export_pdf_select_child, export_pdf_for_child
from handlers.excel_export import export_excel_select_child, export_excel_for_child_cb
from handlers.admin import cmd_grant, cmd_revoke, cmd_stats, cmd_users, cmd_broadcast, check_premium_expiry
from handlers.medications import (
    show_medications_menu, show_meds_child_cb, start_add_medication,
    got_med_name, got_med_dose, got_med_interval, got_med_enddate,
    show_stop_list, stop_medication, cancel_med,
    MED_CHILD, MED_NAME, MED_DOSE, MED_INTERVAL, MED_ENDDATE,
)
from handlers.illness import (
    show_illness_menu, show_illness_child_cb, start_new_illness, got_illness_name,
    start_add_entry, got_entry_temp, got_entry_symptoms, got_entry_meds, got_entry_notes,
    end_illness_cb, show_illness_history, cancel_illness,
    ILL_CHILD, ILL_NAME, ILL_ENTRY_TEMP, ILL_ENTRY_SYM, ILL_ENTRY_MEDS, ILL_ENTRY_NOTES,
)
from handlers.checkups import (
    show_checkups_menu, show_checkups_for_child_cb,
    show_all_checkups_cb, send_checkup_reminders,
    show_mark_checkup_list_cb, mark_checkup_done_cb,
)
from handlers.medical_info import (
    show_medical_info_menu, show_medical_info_child_cb,
    set_blood_group_cb, got_blood_group_cb, got_blood_rh_cb,
    set_policy_cb, got_policy_number, got_policy_company, got_snils,
    start_add_allergy_cb, got_allergy_name, got_allergy_reaction, got_allergy_severity_cb,
    show_allergy_delete_list_cb, delete_allergy_cb,
    start_add_contra_cb, got_contra_name,
    show_contra_delete_list_cb, delete_contra_cb,
    cancel_mi,
    MI_POLICY_NUMBER, MI_POLICY_COMPANY, MI_SNILS,
    MI_ALLERGY_NAME, MI_ALLERGY_REACTION, MI_ALLERGY_SEVERITY,
    MI_CONTRA_NAME,
)
from handlers.referral import show_referral_menu, handle_referral_start
from handlers.ai_assistant import (
    show_ai_menu, start_analyze_doc, got_document_for_analysis,
    show_ai_advice, cancel_ai,
    AI_WAIT_DOC,
)
from handlers.onboarding import (
    start_onboarding, onboarding_step_cb, finish_onboarding_cb,
)
from handlers.pregnancy import (
    show_pregnancy_menu, start_set_pdr_cb, got_pdr_date,
    show_hospital_bag_cb, pregnancy_born_cb, cancel_preg,
    PREG_DATE,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TRIAL_DAYS = 14
TZ = ZoneInfo(os.environ.get("BOT_TIMEZONE", "Europe/Moscow"))

# ── Кнопки нижней клавиатуры ─────────────────────────────────────────────────
BTN_CHILD        = "👶 Ребёнок"
BTN_GROWTH       = "📏 Рост и вес"
BTN_VACCINES     = "💉 Прививки"
BTN_REMINDERS    = "🔔 Напоминания"
BTN_MEDICATIONS  = "💊 Лекарства"
BTN_ILLNESS      = "🤒 Болезни"
BTN_SUBSCRIPTION = "⭐ Подписка"
BTN_PDF          = "📄 PDF"
BTN_CHECKUPS     = "🏥 Осмотры"
BTN_EXCEL        = "📊 Excel"
BTN_MEDICAL      = "🩺 Медкарта"
BTN_CHAT         = "💬 Чат мам"
BTN_PREGNANCY    = "🤰 Беременность"
BTN_AI           = "🤖 ИИ-ассистент"
BTN_PAGE2        = "➡️ Ещё"
BTN_PAGE1        = "⬅️ Назад"

CHAT_URL = os.environ.get("CHAT_URL", "")

MENU_BUTTONS = [
    BTN_CHILD, BTN_GROWTH, BTN_VACCINES, BTN_REMINDERS,
    BTN_MEDICATIONS, BTN_ILLNESS, BTN_SUBSCRIPTION, BTN_PDF,
    BTN_CHECKUPS, BTN_EXCEL, BTN_MEDICAL, BTN_CHAT,
    BTN_PREGNANCY, BTN_AI, BTN_PAGE2, BTN_PAGE1,
]

# Страница 1 — основные функции
PAGE1_KEYBOARD = [
    [BTN_CHILD,       BTN_GROWTH],
    [BTN_VACCINES,    BTN_CHECKUPS],
    [BTN_MEDICATIONS, BTN_ILLNESS],
    [BTN_REMINDERS,   BTN_PAGE2],
]

# Страница 2 — дополнительные
PAGE2_KEYBOARD = [
    [BTN_MEDICAL,     BTN_PDF],
    [BTN_EXCEL,       BTN_SUBSCRIPTION],
    [BTN_PREGNANCY,   BTN_CHAT],
    [BTN_AI,          BTN_PAGE1],
]


def main_reply_keyboard(page=1):
    kb = PAGE1_KEYBOARD if page == 1 else PAGE2_KEYBOARD
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, is_persistent=True)


# ── Старт ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new = db.upsert_user(user.id, user.username, user.first_name)
    name = user.first_name or "Мамочка"

    # Реферальная ссылка
    args = context.args
    if args and args[0].startswith("ref"):
        import asyncio
        asyncio.create_task(handle_referral_start(user.id, args[0], context.application))

    if is_new:
        until = db.activate_trial(user.id)
        until_str = datetime.fromisoformat(until).strftime("%d.%m.%Y") if until else ""
        welcome = (
            f"Привет, {name}! 🌸\n\n"
            f"Добро пожаловать в *МамаБот* — помощник для мам!\n\n"
            f"🎁 *Активирован бесплатный период на {TRIAL_DAYS} дней* (до {until_str}).\n\n"
            f"Выберите раздел в меню ниже 👇"
        )
        await update.message.reply_text(
            welcome, parse_mode="Markdown",
            reply_markup=main_reply_keyboard(1)
        )
        # Запускаем онбординг для новых пользователей
        await start_onboarding(update, context)
    else:
        # Ищем ближайшую прививку среди всех детей
        from datetime import date as _date
        children = db.get_children(user.id)
        hint = ""
        earliest_days = None
        earliest_text = ""
        today = _date.today()
        for ch in children:
            vaccines = db.get_vaccinations(ch["id"], user.id)
            for v in vaccines:
                if v["done_date"] or not v["scheduled_date"]:
                    continue
                try:
                    sched = datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date()
                except Exception:
                    continue
                days_left = (sched - today).days
                if days_left >= 0 and (earliest_days is None or days_left < earliest_days):
                    earliest_days = days_left
                    if days_left == 0:
                        label = "сегодня"
                    elif days_left == 1:
                        label = "завтра"
                    else:
                        label = f"через {days_left} дн."
                    earliest_text = f"\n\n💉 Ближайшая прививка — *{v['vaccine_name']}* ({ch['name']}) {label}"
        hint = earliest_text

        welcome = (
            f"С возвращением, {name}! 🌸"
            f"{hint}\n\n"
            f"Выберите раздел в меню ниже 👇"
        )
        await update.message.reply_text(
            welcome, parse_mode="Markdown",
            reply_markup=main_reply_keyboard(1)
        )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает пользователю его Telegram ID — нажимаемый для копирования."""
    user = update.effective_user
    user_id = user.id
    await update.message.reply_text(
        f"🪪 *Ваш Telegram ID:*\n\n`{user_id}`\n\n"
        f"_Нажмите на цифры выше — они скопируются в буфер обмена._",
        parse_mode="Markdown"
    )


# ── Роутинг кнопок клавиатуры ────────────────────────────────────────────────

async def route_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == BTN_CHILD:
        await show_children_menu(update, context)
    elif text == BTN_GROWTH:
        await show_growth_menu(update, context, child_id=None)
    elif text == BTN_VACCINES:
        await show_vaccines_menu(update, context, child_id=None)
    elif text == BTN_REMINDERS:
        await show_reminders_menu(update, context)
    elif text == BTN_MEDICATIONS:
        await show_medications_menu(update, context)
    elif text == BTN_ILLNESS:
        await show_illness_menu(update, context)
    elif text == BTN_SUBSCRIPTION:
        await show_subscription_menu(update, context)
    elif text == BTN_PDF:
        await export_pdf_select_child(update, context)
    elif text == BTN_CHECKUPS:
        await show_checkups_menu(update, context)
    elif text == BTN_EXCEL:
        await export_excel_select_child(update, context)
    elif text == BTN_MEDICAL:
        await show_medical_info_menu(update, context)
    elif text == BTN_CHAT:
        chat_url = os.environ.get("CHAT_URL", "")
        if chat_url:
            keyboard = [[InlineKeyboardButton("💬 Открыть чат мам", url=chat_url)]]
            await update.message.reply_text(
                "💬 *Чат мам МамаБота*\n\nОбщайтесь, задавайте вопросы, делитесь опытом!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("Чат скоро будет добавлен!")
    elif text == BTN_PREGNANCY:
        await show_pregnancy_menu(update, context)
    elif text == BTN_AI:
        await show_ai_menu(update, context)
    elif text == BTN_PAGE2:
        await update.message.reply_text(
            "👇",
            reply_markup=main_reply_keyboard(2)
        )
    elif text == BTN_PAGE1:
        await update.message.reply_text(
            "👇",
            reply_markup=main_reply_keyboard(1)
        )


async def route_growth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_growth_menu(update, context, child_id=None)


async def route_vaccines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_vaccines_menu(update, context, child_id=None)


async def goto_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    query.data = "subscription"
    await show_subscription_menu(update, context)


# ── Планировщик ──────────────────────────────────────────────────────────────

async def check_reminders(app: Application):
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    due = db.get_due_reminders(now)
    for r in due:
        # Отправляем всем членам семьи
        family_ids = db.get_family_user_ids(r["user_id"])
        for uid in family_ids:
            try:
                await app.bot.send_message(
                    chat_id=uid,
                    text=f"🔔 *Напоминание!*\n\n{r['title']}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Reminder {r['id']} to {uid} failed: {e}")
        db.deactivate_reminder(r["id"])


async def check_medications(app: Application):
    now = datetime.now(TZ)
    meds = db.get_all_active_medications()
    for m in meds:
        try:
            next_at = datetime.fromisoformat(m["next_reminder_at"])
            if next_at.tzinfo is None:
                next_at = next_at.replace(tzinfo=TZ)
        except Exception:
            continue

        if m["end_date"]:
            try:
                end = datetime.strptime(m["end_date"], "%d.%m.%Y").replace(tzinfo=TZ)
                if now > end:
                    conn = db.get_conn()
                    c = conn.cursor()
                    c.execute(db._q("UPDATE medications SET is_active=0 WHERE id=?"), (m["id"],))
                    conn.commit()
                    conn.close()
                    continue
            except Exception:
                pass

        if now >= next_at:
            dose_str = f" · {m['dose']}" if m["dose"] else ""
            family_ids = db.get_family_user_ids(m["user_id"])
            for uid in family_ids:
                try:
                    await app.bot.send_message(
                        chat_id=uid,
                        text=f"💊 *Время принять лекарство!*\n\n{m['name']}{dose_str}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Med reminder {m['id']} to {uid} failed: {e}")
            db.update_medication_next_reminder(m["id"], m["interval_hours"])


async def send_weekly_vaccine_reminders(app: Application):
    from datetime import date, timedelta

    conn = db.get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM children")
    if db._is_pg():
        users = [dict(zip([d[0] for d in c.description], row)) for row in c.fetchall()]
    else:
        users = c.fetchall()
    conn.close()

    today = date.today()
    in_14 = today + timedelta(days=14)

    for user_row in users:
        user_id = user_row["user_id"] if isinstance(user_row, dict) else user_row[0]
        children = db.get_children(user_id)
        messages = []

        for ch in children:
            vaccines = db.get_vaccinations(ch["id"], user_id)
            emoji = "👧" if ch["gender"] == "girl" else "👦"
            upcoming = []
            for v in vaccines:
                if v["done_date"] or not v["scheduled_date"]:
                    continue
                try:
                    sched = datetime.strptime(v["scheduled_date"], "%d.%m.%Y").date()
                except Exception:
                    continue
                if today <= sched <= in_14:
                    days_left = (sched - today).days
                    label = "сегодня" if days_left == 0 else ("завтра" if days_left == 1 else f"через {days_left} дн.")
                    upcoming.append(f"  • {v['vaccine_name']} — {label} ({v['scheduled_date']})")

            if upcoming:
                messages.append(f"{emoji} *{ch['name']}:*\n" + "\n".join(upcoming))

        if messages:
            text = "💉 *Напоминание о прививках*\n\n" + "\n\n".join(messages)
            family_ids = db.get_family_user_ids(user_id)
            for i_uid, uid in enumerate(family_ids):
                try:
                    await app.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Weekly vaccine reminder failed for {uid}: {e}")
                if (i_uid + 1) % 25 == 0:
                    import asyncio
                    await asyncio.sleep(1)


# ── Точка входа ──────────────────────────────────────────────────────────────

def main():
    db.init_db()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(token).build()
    kb_filter = filters.Text(MENU_BUTTONS)

    # ── Диалоги ──────────────────────────────────────────────────────────────
    add_child_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_child, pattern="^child_add$")],
        states={
            CHILD_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_child_name)],
            CHILD_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_child_date)],
            CHILD_GENDER: [CallbackQueryHandler(got_child_gender, pattern="^gender_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_add), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    add_growth_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_growth, pattern="^growth_add:")],
        states={
            GROWTH_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_growth_height)],
            GROWTH_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_growth_weight)],
            GROWTH_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_growth_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel_growth), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    add_reminder_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_reminder, pattern="^reminder_add$")],
        states={
            REM_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_reminder_title)],
            REM_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_reminder_date)],
            REM_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_reminder_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel_reminder), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    add_family_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_family, pattern="^family_add$")],
        states={
            FAMILY_ADD_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_family_member_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel_family), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    add_med_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_medication, pattern="^med_add:")],
        states={
            MED_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_med_name)],
            MED_DOSE:     [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_med_dose)],
            MED_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_med_interval)],
            MED_ENDDATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_med_enddate)],
        },
        fallbacks=[CommandHandler("cancel", cancel_med), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    add_illness_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_new_illness, pattern="^ill_new:")],
        states={
            ILL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_illness_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel_illness), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    add_illness_entry_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_entry, pattern="^ill_add_entry:")],
        states={
            ILL_ENTRY_TEMP:  [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_entry_temp)],
            ILL_ENTRY_SYM:   [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_entry_symptoms)],
            ILL_ENTRY_MEDS:  [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_entry_meds)],
            ILL_ENTRY_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_entry_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel_illness), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    pregnancy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_set_pdr_cb, pattern="^preg_set_pdr$")],
        states={
            PREG_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_pdr_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel_preg), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    policy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_policy_cb, pattern="^mi_policy:")],
        states={
            MI_POLICY_NUMBER:  [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_policy_number)],
            MI_POLICY_COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_policy_company)],
            MI_SNILS:          [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_snils)],
        },
        fallbacks=[CommandHandler("cancel", cancel_mi), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    allergy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_allergy_cb, pattern="^mi_allergy_add:")],
        states={
            MI_ALLERGY_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_allergy_name)],
            MI_ALLERGY_REACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_allergy_reaction)],
            MI_ALLERGY_SEVERITY: [CallbackQueryHandler(got_allergy_severity_cb, pattern="^mi_asev:")],
        },
        fallbacks=[CommandHandler("cancel", cancel_mi), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    contra_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_contra_cb, pattern="^mi_contra_add:")],
        states={
            MI_CONTRA_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_contra_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel_mi), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    analyze_doc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_analyze_doc, pattern="^ai_analyze_doc$")],
        states={
            AI_WAIT_DOC: [
                MessageHandler(filters.PHOTO, got_document_for_analysis),
                MessageHandler(filters.Document.ALL, got_document_for_analysis),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_ai), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    # ── Команды ──────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("id",        cmd_id))
    app.add_handler(CommandHandler("grant",     cmd_grant))
    app.add_handler(CommandHandler("revoke",    cmd_revoke))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("users",     cmd_users))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # ── Диалоги ──────────────────────────────────────────────────────────────
    app.add_handler(add_child_conv)
    app.add_handler(add_growth_conv)
    app.add_handler(add_reminder_conv)
    app.add_handler(add_family_conv)
    app.add_handler(add_med_conv)
    app.add_handler(add_illness_conv)
    app.add_handler(add_illness_entry_conv)
    app.add_handler(pregnancy_conv)
    app.add_handler(policy_conv)
    app.add_handler(allergy_conv)
    app.add_handler(contra_conv)
    app.add_handler(analyze_doc_conv)

    # ── Кнопки клавиатуры ────────────────────────────────────────────────────
    app.add_handler(MessageHandler(kb_filter, route_keyboard))

    # ── Онбординг ────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(onboarding_step_cb,   pattern="^onboard:\\d+$"))
    app.add_handler(CallbackQueryHandler(finish_onboarding_cb, pattern="^onboard_done$"))

    # ── Дети ─────────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_children_menu,  pattern="^my_child$"))
    app.add_handler(CallbackQueryHandler(show_child_detail,   pattern="^child_view:"))
    app.add_handler(CallbackQueryHandler(confirm_delete_child, pattern="^child_delete:"))
    app.add_handler(CallbackQueryHandler(do_delete_child,     pattern="^child_delete_confirm:"))

    # ── Рост ─────────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(route_growth,       pattern="^growth$"))
    app.add_handler(CallbackQueryHandler(show_growth_menu,   pattern="^growth_menu:"))

    # ── Прививки ─────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(route_vaccines,      pattern="^vaccines$"))
    app.add_handler(CallbackQueryHandler(show_vaccines_menu,  pattern="^vaccines_menu:"))
    app.add_handler(CallbackQueryHandler(show_vaccines_list,  pattern="^vaccines_list:"))
    app.add_handler(CallbackQueryHandler(show_done_list,      pattern="^vaccines_done_list:"))
    app.add_handler(CallbackQueryHandler(mark_vaccine_done,   pattern="^vac_mark:"))

    # ── Осмотры ──────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_checkups_menu,          pattern="^checkups$"))
    app.add_handler(CallbackQueryHandler(show_checkups_for_child_cb,  pattern="^checkup_child:"))
    app.add_handler(CallbackQueryHandler(show_all_checkups_cb,        pattern="^checkup_all:"))
    app.add_handler(CallbackQueryHandler(show_mark_checkup_list_cb,   pattern="^checkup_mark_list:"))
    app.add_handler(CallbackQueryHandler(mark_checkup_done_cb,        pattern="^checkup_mark:"))

    # ── Напоминания ───────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_reminders_menu, pattern="^reminders$"))
    app.add_handler(CallbackQueryHandler(show_delete_list,    pattern="^reminder_delete_list$"))
    app.add_handler(CallbackQueryHandler(do_delete_reminder,  pattern="^reminder_delete:"))

    # ── Подписка ─────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_subscription_menu, pattern="^subscription$"))
    app.add_handler(CallbackQueryHandler(activate_trial,         pattern="^sub_trial$"))
    app.add_handler(CallbackQueryHandler(buy_premium,            pattern="^sub_buy$"))
    app.add_handler(CallbackQueryHandler(goto_subscription,      pattern="^goto_subscription$"))
    app.add_handler(CallbackQueryHandler(show_family_menu,       pattern="^family_menu$"))
    app.add_handler(CallbackQueryHandler(remove_family_member,   pattern="^family_remove:"))

    # ── PDF ──────────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(export_pdf_select_child, pattern="^pdf_select$"))
    app.add_handler(CallbackQueryHandler(export_pdf_for_child,    pattern="^pdf_export:"))

    # ── Excel ─────────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(export_excel_select_child, pattern="^excel_select$"))
    app.add_handler(CallbackQueryHandler(export_excel_for_child_cb, pattern="^excel_export:"))

    # ── Лекарства ────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_meds_child_cb, pattern="^med_child:"))
    app.add_handler(CallbackQueryHandler(show_stop_list,     pattern="^med_stop_list:"))
    app.add_handler(CallbackQueryHandler(stop_medication,    pattern="^med_stop:"))

    # ── Медкарта ─────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_medical_info_menu,       pattern="^medical_info$"))
    app.add_handler(CallbackQueryHandler(show_medical_info_child_cb,   pattern="^mi_child:"))
    app.add_handler(CallbackQueryHandler(set_blood_group_cb,           pattern="^mi_blood:"))
    app.add_handler(CallbackQueryHandler(got_blood_group_cb,           pattern="^mi_bg:"))
    app.add_handler(CallbackQueryHandler(got_blood_rh_cb,              pattern="^mi_rh:"))
    app.add_handler(CallbackQueryHandler(show_allergy_delete_list_cb,  pattern="^mi_allergy_del_list:"))
    app.add_handler(CallbackQueryHandler(delete_allergy_cb,            pattern="^mi_allergy_del:"))
    app.add_handler(CallbackQueryHandler(show_contra_delete_list_cb,   pattern="^mi_contra_del_list:"))
    app.add_handler(CallbackQueryHandler(delete_contra_cb,             pattern="^mi_contra_del:"))

    # ── Реферальная система ───────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_referral_menu, pattern="^referral$"))

    # ── Беременность ──────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_pregnancy_menu,   pattern="^pregnancy$"))
    app.add_handler(CallbackQueryHandler(show_hospital_bag_cb,  pattern="^preg_bag$"))
    app.add_handler(CallbackQueryHandler(pregnancy_born_cb,     pattern="^preg_born$"))

    # ── Болезни ───────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_illness_child_cb, pattern="^ill_child:"))
    app.add_handler(CallbackQueryHandler(end_illness_cb,        pattern="^ill_end:"))
    app.add_handler(CallbackQueryHandler(show_illness_history,  pattern="^ill_history:"))

    # ── ИИ-ассистент ──────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_ai_menu,    pattern="^ai_menu$"))
    app.add_handler(CallbackQueryHandler(show_ai_advice,  pattern="^ai_advice:"))

    # ── Планировщик ──────────────────────────────────────────────────────────
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(check_reminders,               "interval", minutes=1,  args=[app])
    scheduler.add_job(check_medications,             "interval", minutes=1,  args=[app])
    scheduler.add_job(send_weekly_vaccine_reminders, "cron", day_of_week="mon", hour=9, minute=0, args=[app])
    scheduler.add_job(send_checkup_reminders,        "cron", hour=9, minute=0, args=[app])
    scheduler.add_job(check_premium_expiry,          "interval", hours=12, args=[app])
    scheduler.start()

    logger.info("МамаБот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
