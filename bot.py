import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes,
)

import config
import sheets
import analytics
from charts import weekly_chart
from parser import parse_message
from categories import ALL_CATEGORY_NAMES

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
# Отключаем шумные логи запросов к Telegram
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Application").setLevel(logging.WARNING)
log = logging.getLogger("budget-bot")

# Здесь храним незавершённые операции: user_id -> parsed
PENDING = {}


# ============================================================
# Вспомогательные функции
# ============================================================

def fmt_money(x):
    """Форматирует сумму: 12345.6 -> '12 345'."""
    return f"{round(x):,}".replace(",", " ")


def fmt_money_full(x):
    """С копейками, если они есть."""
    if x == int(x):
        return fmt_money(x)
    return f"{x:,.2f}".replace(",", " ")


def category_buttons():
    """Строит клавиатуру с кнопками категорий."""
    rows = []
    row = []
    for cat in ALL_CATEGORY_NAMES:
        row.append(InlineKeyboardButton(cat, callback_data=f"cat:{cat}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="cat:CANCEL")])
    return InlineKeyboardMarkup(rows)


# ============================================================
# Команды
# ============================================================

async def cmd_start(update: Update, _ctx):
    await update.message.reply_text(
        "Привет! Пишите траты и доходы прямо в чат, например:\n"
        "• `250 продукты`\n"
        "• `такси 450`\n"
        "• `подарок 3000`\n"
        "• `продукты 15000 след` — запишет в следующий бюджетный месяц\n\n"
        "*Команды:*\n"
        "/itog — сводка план/факт за текущий период\n"
        "/prognoz — прогноз до конца периода\n"
        "/sravnit — сравнение с прошлым периодом\n"
        "/grafik — график за 7 дней\n"
        "/plany — все планы на текущий период\n"
        "/plan Продукты 25000 — задать план\n"
        "/plan Продукты 30000 след — план на следующий период\n"
        "/otmena — удалить последнюю запись\n"
        "/id — показать ID чата (нужно один раз)",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update, ctx):
    await cmd_start(update, ctx)


async def cmd_id(update, _ctx):
    await update.message.reply_text(
        f"Chat ID: `{update.effective_chat.id}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_cancel(update, _ctx):
    last = sheets.delete_last_operation()
    if not last:
        await update.message.reply_text("Нечего отменять.")
        return
    await update.message.reply_text(
        f"Удалила: {last[0]} · {last[1]} · {fmt_money_full(float(last[2]))} ₽"
    )


async def cmd_summary(update, _ctx):
    label = sheets.current_period_label()
    title = analytics.period_title(label)
    rows = analytics.plan_fact(label)
    s = analytics.summary(label)

    if not rows and s["count"] == 0:
        await update.message.reply_text(
            f"📊 *{title}*\nПока ничего не записано.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"📊 *{title}*", ""]

    # Доходы
    lines.append(f"💰 *Доходы:* {fmt_money(s['income'])} ₽")

    # Расходы — сгруппируем
    lines.append("")
    lines.append("💸 *Расходы:*")
    expense_total = 0
    debt_total = 0
    for r in rows:
        if r["type"] == "income":
            continue
        mark = "⚠️" if r["over"] else "•"
        if r["plan"] > 0:
            line = (f"{mark} {r['category']}: "
                    f"{fmt_money(r['fact'])} / {fmt_money(r['plan'])} ₽")
            if r["over"]:
                line += f" (+{fmt_money(r['fact'] - r['plan'])})"
            lines.append(line)
        else:
            lines.append(f"• {r['category']}: {fmt_money(r['fact'])} ₽")

        if r["type"] == "debt":
            debt_total += r["fact"]
        else:
            expense_total += r["fact"]

    lines.append("")
    lines.append(f"💸 Расходы всего: *{fmt_money(expense_total)} ₽*")
    if debt_total:
        lines.append(f"🏦 Рассрочка: *{fmt_money(debt_total)} ₽*")
    lines.append(f"⚖️ Остаток: *{fmt_money(s['income'] - expense_total - debt_total)} ₽*")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_forecast(update, _ctx):
    f = analytics.forecast()
    title = analytics.period_title(f["label"])

    lines = [f"🔮 *Прогноз на {title}*", ""]
    lines.append(f"Потрачено: {fmt_money(f['spent'])} ₽")
    lines.append(f"Прогноз к концу: *{fmt_money(f['projected'])} ₽*")
    lines.append(f"Дней осталось: {f['days_left']}")

    if f["total_plan"]:
        lines.append("")
        lines.append(f"Общий план: {fmt_money(f['total_plan'])} ₽")
        lines.append(f"Остаток: *{fmt_money(f['remaining'])} ₽*")

    if f["over"]:
        lines.append("")
        lines.append("⚠️ *Превышения:*")
        for o in f["over"]:
            lines.append(
                f"• {o['category']}: "
                f"{fmt_money(o['fact'])} / {fmt_money(o['plan'])} ₽ "
                f"(+{fmt_money(o['diff'])})"
            )
    else:
        lines.append("")
        lines.append("✅ Ни по одной категории не вышли за план")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_compare(update, _ctx):
    diff = analytics.compare_with_prev()
    if not diff:
        await update.message.reply_text("Нет данных для сравнения.")
        return

    lines = ["📈 *Сравнение с прошлым периодом*", ""]
    for cat, cur, prev, pct in diff:
        if pct is None:
            lines.append(f"• {cat}: {fmt_money(cur)} ₽ (новое)")
            continue
        arrow = "🔺" if pct > 0 else ("🔻" if pct < 0 else "➖")
        sign = "+" if pct >= 0 else ""
        lines.append(
            f"{arrow} {cat}: {fmt_money(cur)} ₽ "
            f"({sign}{pct:.0f}%, было {fmt_money(prev)})"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_chart(update, _ctx):
    try:
        png = weekly_chart()
    except Exception as e:
        await update.message.reply_text(f"Не смогла построить график: {e}")
        return
    await update.message.reply_photo(photo=png, caption="Расходы за последние 7 дней")


async def cmd_plans(update, _ctx):
    label = sheets.current_period_label()
    title = analytics.period_title(label)
    plans = sheets.get_all_plans(label)

    if not plans:
        await update.message.reply_text(
            f"На {title} планы не заданы.\n"
            f"Используй `/план Продукты 25000`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"📋 *Планы на {title}*", ""]
    for cat, val in sorted(plans.items()):
        lines.append(f"• {cat}: {fmt_money(val)} ₽")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_plan(update, ctx):
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "Формат: `/план Продукты 25000`\n"
            "Или: `/план Продукты 25000 след` — на следующий период",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Последний аргумент — либо "след", либо сумма
    target_next = False
    if args[-1].lower() in ("след", "следующий"):
        target_next = True
        args = args[:-1]

    if len(args) < 2:
        await update.message.reply_text("Не поняла. Формат: `/план Продукты 25000`",
                                        parse_mode=ParseMode.MARKDOWN)
        return

    try:
        value = float(args[-1].replace(",", ".").replace(" ", ""))
    except ValueError:
        await update.message.reply_text("Не поняла сумму.")
        return

    category = " ".join(args[:-1]).strip()
    if category not in ALL_CATEGORY_NAMES:
        # Попробуем найти по неточному совпадению
        matches = [c for c in ALL_CATEGORY_NAMES if category.lower() in c.lower()]
        if not matches:
            await update.message.reply_text(
                f"Категория «{category}» не найдена. Проверь название.")
            return
        category = matches[0]

    label = sheets.next_period_label() if target_next else sheets.current_period_label()
    sheets.set_plan(label, category, value)

    title = analytics.period_title(label)
    await update.message.reply_text(
        f"✅ План на *{title}*:\n{category} — {fmt_money(value)} ₽",
        parse_mode=ParseMode.MARKDOWN,
    )


# ============================================================
# Обработка сообщений (трат и доходов)
# ============================================================

async def _track_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Запоминаем чат, чтобы знать, куда слать напоминания."""
    if update.effective_chat:
        ctx.bot_data.setdefault("chat_ids", set()).add(update.effective_chat.id)


async def on_message(update: Update, ctx):
    parsed = parse_message(update.message.text)
    if not parsed:
        return

    if parsed["category"] is None:
        # Не угадали — спрашиваем кнопками
        PENDING[update.effective_user.id] = parsed
        await update.message.reply_text(
            f"Куда отнести «{parsed['raw']}» на {fmt_money_full(parsed['amount'])} ₽?",
            reply_markup=category_buttons(),
        )
        return

    # Если "след" — ставим дату начала следующего периода
    op_date = parsed["date"]
    if parsed["next_period"]:
        next_label = sheets.next_period_label()
        op_date, _ = sheets.period_bounds(next_label)

    sheets.append_operation(
        op_date, parsed["category"], parsed["amount"], parsed["raw"])
    # тихо, без ответа — чтобы не засорять чат


async def on_callback(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    data = q.data
    if not data.startswith("cat:"):
        return

    if data == "cat:CANCEL":
        PENDING.pop(q.from_user.id, None)
        await q.edit_message_text("Отменено.")
        return

    category = data[4:]
    parsed = PENDING.pop(q.from_user.id, None)
    if not parsed:
        await q.edit_message_text("Уже неактуально, введи заново.")
        return

    op_date = parsed["date"]
    if parsed["next_period"]:
        next_label = sheets.next_period_label()
        op_date, _ = sheets.period_bounds(next_label)

    sheets.append_operation(
        op_date, category, parsed["amount"], parsed["raw"])
    await q.edit_message_text(
        f"✅ {category}: {fmt_money_full(parsed['amount'])} ₽ "
        f"({op_date.strftime('%d.%m')})"
    )


# ============================================================
# Периодические задачи
# ============================================================

async def job_reminder(ctx):
    """Вечернее напоминание записать траты."""
    chat_ids = set(ctx.bot_data.get("chat_ids", set()))
    if config.CHAT_ID:
        try:
            chat_ids.add(int(config.CHAT_ID))
        except (ValueError, TypeError):
            pass
    for cid in chat_ids:
        try:
            await ctx.bot.send_message(
                cid,
                "🍽 Не забудьте записать сегодняшние траты, если ещё нет."
            )
        except Exception as e:
            log.warning("Reminder failed for %s: %s", cid, e)


async def job_weekly_chart(ctx):
    """Воскресный график за неделю."""
    chat_ids = set(ctx.bot_data.get("chat_ids", set()))
    if config.CHAT_ID:
        try:
            chat_ids.add(int(config.CHAT_ID))
        except (ValueError, TypeError):
            pass
    try:
        png = weekly_chart()
    except Exception as e:
        log.warning("Chart building failed: %s", e)
        return
    for cid in chat_ids:
        try:
            await ctx.bot.send_photo(cid, png, caption="📅 Расходы за неделю")
        except Exception as e:
            log.warning("Weekly chart failed for %s: %s", cid, e)


# ============================================================
# Запуск
# ============================================================

def main():
    log.info("Инициализация таблицы…")
    sheets.init_sheets()

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Сначала — запоминаем все чаты (на любые апдейты)
    app.add_handler(MessageHandler(filters.ALL, _track_chat), group=-1)

    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("itog", cmd_summary))
    app.add_handler(CommandHandler("prognoz", cmd_forecast))
    app.add_handler(CommandHandler("sravnit", cmd_compare))
    app.add_handler(CommandHandler("grafik", cmd_chart))
    app.add_handler(CommandHandler("plany", cmd_plans))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("otmena", cmd_cancel))

    # Кнопки
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^cat:"))

    # Обычные сообщения — парсим как траты
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    # Периодические задачи
    tz = ZoneInfo(config.TIMEZONE)
    jq = app.job_queue
    jq.run_daily(
        job_reminder,
        time=time(config.REMINDER_HOUR, config.REMINDER_MINUTE, tzinfo=tz),
        name="daily-reminder",
    )
    jq.run_daily(
        job_weekly_chart,
        time=time(20, 0, tzinfo=tz),
        days=(6,),  # воскресенье
        name="weekly-chart",
    )

    log.info("Бот запущен. Жду сообщений…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()