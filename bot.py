import os
import logging
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup
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
from handlers.admin import cmd_grant, cmd_revoke, cmd_stats, cmd_users, cmd_broadcast, check_premium_expiry
from handlers.photo_diary import (
    show_photo_menu, show_child_photos_cb, start_add_photo,
    select_child_for_photo, got_photo, got_photo_caption,
    show_photo_view_list, show_single_photo, delete_photo_cb, cancel_photo,
    PHOTO_WAIT, PHOTO_CHILD, PHOTO_CAPTION,
)
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TRIAL_DAYS = 14

# ── Кнопки нижней клавиатуры ─────────────────────────────────────────────────
BTN_CHILD       = "👶 Мой ребёнок"
BTN_GROWTH      = "📏 Рост и вес"
BTN_VACCINES    = "💉 Прививки"
BTN_REMINDERS   = "🔔 Напоминания"
BTN_PHOTOS      = "📷 Фотодневник"
BTN_MEDICATIONS = "💊 Лекарства"
BTN_ILLNESS     = "🤒 Болезни"
BTN_SUBSCRIPTION = "⭐ Подписка"

MENU_BUTTONS = [
    BTN_CHILD, BTN_GROWTH, BTN_VACCINES, BTN_REMINDERS,
    BTN_PHOTOS, BTN_MEDICATIONS, BTN_ILLNESS, BTN_SUBSCRIPTION,
]


def main_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            [BTN_CHILD,    BTN_GROWTH],
            [BTN_VACCINES, BTN_REMINDERS],
            [BTN_PHOTOS,   BTN_MEDICATIONS],
            [BTN_ILLNESS,  BTN_SUBSCRIPTION],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ── Старт ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new = db.upsert_user(user.id, user.username, user.first_name)
    name = user.first_name or "Мамочка"

    if is_new:
        until = db.activate_trial(user.id)
        until_str = datetime.fromisoformat(until).strftime("%d.%m.%Y") if until else ""
        welcome = (
            f"Привет, {name}! 🌸\n\n"
            f"Добро пожаловать в *МамаБот* — помощник для мам!\n\n"
            f"🎁 *Вам активирован бесплатный период на {TRIAL_DAYS} дней* (до {until_str}).\n"
            f"Все Premium-функции уже доступны:\n"
            f"• Неограниченное количество детей\n"
            f"• Полная история роста и веса\n"
            f"• Прививки и напоминания\n"
            f"• Фотодневник, лекарства, журнал болезней\n"
            f"• PDF-экспорт и семейный доступ\n\n"
            f"После пробного периода — *300 ₽/мес*.\n\n"
            f"Выберите раздел в меню ниже 👇"
        )
    else:
        welcome = (
            f"С возвращением, {name}! 🌸\n\n"
            f"Выберите раздел в меню ниже 👇"
        )

    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard()
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
    elif text == BTN_PHOTOS:
        await show_photo_menu(update, context)
    elif text == BTN_MEDICATIONS:
        await show_medications_menu(update, context)
    elif text == BTN_ILLNESS:
        await show_illness_menu(update, context)
    elif text == BTN_SUBSCRIPTION:
        await show_subscription_menu(update, context)


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
    due = db.get_due_reminders()
    for r in due:
        try:
            await app.bot.send_message(
                chat_id=r["user_id"],
                text=f"🔔 *Напоминание!*\n\n{r['title']}",
                parse_mode="Markdown"
            )
            db.deactivate_reminder(r["id"])
        except Exception as e:
            logger.error(f"Reminder {r['id']} failed: {e}")


async def check_medications(app: Application):
    now = datetime.now()
    meds = db.get_all_active_medications()
    for m in meds:
        try:
            next_at = datetime.fromisoformat(m["next_reminder_at"])
        except Exception:
            continue

        if m["end_date"]:
            try:
                end = datetime.strptime(m["end_date"], "%d.%m.%Y")
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
            try:
                await app.bot.send_message(
                    chat_id=m["user_id"],
                    text=f"💊 *Время принять лекарство!*\n\n{m['name']}{dose_str}",
                    parse_mode="Markdown"
                )
                db.update_medication_next_reminder(m["id"], m["interval_hours"])
            except Exception as e:
                logger.error(f"Med reminder {m['id']} failed: {e}")


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
            try:
                await app.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Weekly vaccine reminder failed for {user_id}: {e}")


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

    add_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_photo, pattern="^photo_add$")],
        states={
            PHOTO_CHILD:   [CallbackQueryHandler(select_child_for_photo, pattern="^photo_sel_child:")],
            PHOTO_WAIT:    [MessageHandler(filters.PHOTO, got_photo)],
            PHOTO_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_photo_caption)],
        },
        fallbacks=[CommandHandler("cancel", cancel_photo), MessageHandler(kb_filter, route_keyboard)],
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
            ILL_ENTRY_TEMP: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_entry_temp)],
            ILL_ENTRY_SYM:  [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_entry_symptoms)],
            ILL_ENTRY_MEDS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_entry_meds)],
            ILL_ENTRY_NOTES:[MessageHandler(filters.TEXT & ~filters.COMMAND & ~kb_filter, got_entry_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel_illness), MessageHandler(kb_filter, route_keyboard)],
        allow_reentry=True,
    )

    # ── Команды ──────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("grant", cmd_grant))
    app.add_handler(CommandHandler("revoke", cmd_revoke))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # ── Диалоги (до общего обработчика текста) ───────────────────────────────
    app.add_handler(add_child_conv)
    app.add_handler(add_growth_conv)
    app.add_handler(add_reminder_conv)
    app.add_handler(add_family_conv)
    app.add_handler(add_photo_conv)
    app.add_handler(add_med_conv)
    app.add_handler(add_illness_conv)
    app.add_handler(add_illness_entry_conv)

    # ── Кнопки нижней клавиатуры ─────────────────────────────────────────────
    app.add_handler(MessageHandler(kb_filter, route_keyboard))

    # ── Inline callbacks: дети ───────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_children_menu, pattern="^my_child$"))
    app.add_handler(CallbackQueryHandler(show_child_detail, pattern="^child_view:"))
    app.add_handler(CallbackQueryHandler(confirm_delete_child, pattern="^child_delete:"))
    app.add_handler(CallbackQueryHandler(do_delete_child, pattern="^child_delete_confirm:"))

    # ── Inline callbacks: рост ───────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(route_growth, pattern="^growth$"))
    app.add_handler(CallbackQueryHandler(show_growth_menu, pattern="^growth_menu:"))

    # ── Inline callbacks: прививки ───────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(route_vaccines, pattern="^vaccines$"))
    app.add_handler(CallbackQueryHandler(show_vaccines_menu, pattern="^vaccines_menu:"))
    app.add_handler(CallbackQueryHandler(show_vaccines_list, pattern="^vaccines_list:"))
    app.add_handler(CallbackQueryHandler(show_done_list, pattern="^vaccines_done_list:"))
    app.add_handler(CallbackQueryHandler(mark_vaccine_done, pattern="^vac_mark:"))

    # ── Inline callbacks: напоминания ────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_reminders_menu, pattern="^reminders$"))
    app.add_handler(CallbackQueryHandler(show_delete_list, pattern="^reminder_delete_list$"))
    app.add_handler(CallbackQueryHandler(do_delete_reminder, pattern="^reminder_delete:"))

    # ── Inline callbacks: подписка ───────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_subscription_menu, pattern="^subscription$"))
    app.add_handler(CallbackQueryHandler(activate_trial, pattern="^sub_trial$"))
    app.add_handler(CallbackQueryHandler(buy_premium, pattern="^sub_buy$"))
    app.add_handler(CallbackQueryHandler(goto_subscription, pattern="^goto_subscription$"))
    app.add_handler(CallbackQueryHandler(show_family_menu, pattern="^family_menu$"))
    app.add_handler(CallbackQueryHandler(remove_family_member, pattern="^family_remove:"))

    # ── Inline callbacks: PDF ────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(export_pdf_select_child, pattern="^pdf_select$"))
    app.add_handler(CallbackQueryHandler(export_pdf_for_child, pattern="^pdf_export:"))

    # ── Inline callbacks: фотодневник ────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_child_photos_cb, pattern="^photo_child_view:"))
    app.add_handler(CallbackQueryHandler(show_photo_view_list, pattern="^photo_view_list:"))
    app.add_handler(CallbackQueryHandler(show_single_photo, pattern="^photo_show:"))
    app.add_handler(CallbackQueryHandler(delete_photo_cb, pattern="^photo_delete:"))

    # ── Inline callbacks: лекарства ──────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_meds_child_cb, pattern="^med_child:"))
    app.add_handler(CallbackQueryHandler(show_stop_list, pattern="^med_stop_list:"))
    app.add_handler(CallbackQueryHandler(stop_medication, pattern="^med_stop:"))

    # ── Inline callbacks: болезни ────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(show_illness_child_cb, pattern="^ill_child:"))
    app.add_handler(CallbackQueryHandler(end_illness_cb, pattern="^ill_end:"))
    app.add_handler(CallbackQueryHandler(show_illness_history, pattern="^ill_history:"))

    # ── Планировщик ──────────────────────────────────────────────────────────
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[app])
    scheduler.add_job(check_medications, "interval", minutes=1, args=[app])
    scheduler.add_job(
        send_weekly_vaccine_reminders,
        "cron", day_of_week="mon", hour=9, minute=0, args=[app]
    )
    scheduler.add_job(check_premium_expiry, "interval", hours=12, args=[app])
    scheduler.start()

    logger.info("МамаБот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
