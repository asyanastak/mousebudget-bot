from datetime import date, timedelta
from calendar import monthrange

from sheets import (
    operations_in_period, period_bounds,
    current_period_label, next_period_label,
    get_plan, get_all_plans,
)
from categories import CATEGORIES, get_type


def summary(period_label=None):
    """
    Сводка по бюджетному периоду.
    Возвращает:
    {
        "label": "2026-10",
        "start": date, "end": date,
        "by_cat": {категория: сумма},
        "income": сумма доходов,
        "expense": сумма расходов,
        "debt": сумма долгов,
        "by_type": {income: [...], expense: [...], debt: [...]},
    }
    """
    label = period_label or current_period_label()
    start, end = period_bounds(label)
    ops = operations_in_period(label)

    by_cat = {}
    by_type = {"income": {}, "expense": {}, "debt": {}}
    total_income = total_expense = total_debt = 0.0

    for o in ops:
        cat = o["category"]
        amt = o["amount"]
        by_cat[cat] = by_cat.get(cat, 0) + amt

        t = get_type(cat) or "expense"
        by_type[t][cat] = by_type[t].get(cat, 0) + amt

        if t == "income":
            total_income += amt
        elif t == "debt":
            total_debt += amt
        else:
            total_expense += amt

    return {
        "label": label,
        "start": start,
        "end": end,
        "by_cat": by_cat,
        "by_type": by_type,
        "income": total_income,
        "expense": total_expense,
        "debt": total_debt,
        "count": len(ops),
    }


def plan_fact(period_label=None):
    """
    План/факт по категориям за период.
    Возвращает список:
    [
        {category, type, plan, fact, diff, pct, over},
        ...
    ]
    """
    label = period_label or current_period_label()
    s = summary(label)
    plans = get_all_plans(label)

    rows = []
    for cat, meta in CATEGORIES.items():
        ctype = meta["type"]
        plan = plans.get(cat, 0)
        fact = s["by_cat"].get(cat, 0)
        if plan == 0 and fact == 0:
            continue
        diff = plan - fact
        pct = (fact / plan * 100) if plan > 0 else 0
        over = (plan > 0 and fact > plan)
        rows.append({
            "category": cat,
            "type": ctype,
            "plan": plan,
            "fact": fact,
            "diff": diff,
            "pct": pct,
            "over": over,
        })

    # Сортируем: сначала превышения, потом по убыванию факта
    rows.sort(key=lambda r: (not r["over"], -r["fact"]))
    return rows


def forecast(period_label=None):
    """
    Прогноз до конца периода и остаток по общему плану.
    """
    label = period_label or current_period_label()
    start, end = period_bounds(label)
    today = date.today()

    # Сколько дней периода прошло
    if today < start:
        # период ещё не начался
        days_passed = 0
    elif today > end:
        # период закончился
        days_passed = (end - start).days + 1
    else:
        days_passed = (today - start).days + 1

    days_total = (end - start).days + 1
    days_left = max(days_total - days_passed, 0)

    s = summary(label)
    plans = get_all_plans(label)
    total_plan = sum(plans.values())
    total_fact = s["expense"] + s["debt"]

    if days_passed > 0:
        avg_per_day = total_fact / days_passed
        projected = avg_per_day * days_total
    else:
        avg_per_day = 0
        projected = 0

    remaining = total_plan - total_fact if total_plan else None

    # Превышения
    over = []
    for cat, meta in CATEGORIES.items():
        if meta["type"] not in ("expense", "debt"):
            continue
        plan = plans.get(cat, 0)
        fact = s["by_cat"].get(cat, 0)
        if plan > 0 and fact > plan:
            over.append({"category": cat, "plan": plan, "fact": fact,
                         "diff": fact - plan})

    return {
        "label": label,
        "spent": total_fact,
        "projected": projected,
        "days_passed": days_passed,
        "days_left": days_left,
        "total_plan": total_plan or None,
        "remaining": remaining,
        "over": over,
        "income": s["income"],
    }


def compare_with_prev(period_label=None):
    """
    Сравнение текущего периода с предыдущим по категориям.
    Возвращает список [(category, cur, prev, pct_change)].
    """
    label = period_label or current_period_label()
    # Предыдущий период
    y, m = map(int, label.split("-"))
    if m == 1:
        prev_label = f"{y - 1:04d}-12"
    else:
        prev_label = f"{y:04d}-{m - 1:02d}"

    cur = summary(label)["by_cat"]
    prev = summary(prev_label)["by_cat"]

    cats = set(cur) | set(prev)
    result = []
    for c in cats:
        c_val = cur.get(c, 0)
        p_val = prev.get(c, 0)
        if c_val == 0 and p_val == 0:
            continue
        if p_val == 0:
            pct = None  # новое
        else:
            pct = (c_val - p_val) / p_val * 100
        result.append((c, c_val, p_val, pct))

    result.sort(key=lambda x: -x[1])
    return result


def category_status(category, period_label=None):
    """
    Статус одной категории: сколько потрачено, сколько осталось, превышение ли.
    """
    label = period_label or current_period_label()
    s = summary(label)
    plans = get_all_plans(label)
    plan = plans.get(category, 0)
    fact = s["by_cat"].get(category, 0)
    diff = plan - fact
    over = plan > 0 and fact > plan
    pct = (fact / plan * 100) if plan > 0 else 0
    return {
        "category": category,
        "plan": plan,
        "fact": fact,
        "diff": diff,
        "over": over,
        "pct": pct,
    }


def month_name_ru(month_num):
    """Название месяца по-русски для красивых сообщений."""
    names = ["январь", "февраль", "март", "апрель", "май", "июнь",
             "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
    return names[month_num - 1]


def period_title(label):
    """'2026-10' -> 'октябрь 2026 (10.10–09.11)'."""
    y, m = map(int, label.split("-"))
    start, end = period_bounds(label)
    return (f"{month_name_ru(m)} {y} "
            f"({start.strftime('%d.%m')}–{end.strftime('%d.%m')})")