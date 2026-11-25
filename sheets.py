import gspread
from google.oauth2.service_account import Credentials
from datetime import date, timedelta
from calendar import monthrange

from config import (
    GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID,
    OPS_SHEET, CATS_SHEET, SUMMARY_SHEET, PLANS_SHEET,
    BUDGET_START_DAY,
)
from categories import CATEGORIES, get_type

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_client = None
_spreadsheet = None


def _get_spreadsheet():
    """Ленивая авторизация в Google Sheets."""
    global _client, _spreadsheet
    if _spreadsheet is None:
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(SPREADSHEET_ID)
    return _spreadsheet


def _ws(name):
    """Получить лист по имени. Если нет — создать."""
    try:
        return _get_spreadsheet().worksheet(name)
    except gspread.WorksheetNotFound:
        return _get_spreadsheet().add_worksheet(title=name, rows=1000, cols=10)


def init_sheets():
    """Создаёт все листы и заголовки, если их нет."""
    # Лист Операции
    ops = _ws(OPS_SHEET)
    if ops.row_values(1)[:4] != ["Дата", "Категория", "Сумма", "Комментарий"]:
        ops.clear()
        ops.insert_row(["Дата", "Категория", "Сумма", "Комментарий"], 1)

    # Лист Категории
    cats = _ws(CATS_SHEET)
    if cats.row_values(1)[:2] != ["Категория", "Тип"]:
        cats.clear()
        cats.insert_row(["Категория", "Тип"], 1)
        # Заполняем из categories.py
        rows = [[name, meta["type"]] for name, meta in CATEGORIES.items()]
        if rows:
            cats.append_rows(rows)

    # Лист Сводка (пока просто заготовка)
    summary = _ws(SUMMARY_SHEET)
    if not summary.row_values(1):
        summary.insert_row(["Категория", "План", "Факт", "Остаток"], 1)

    # Лист Планы
    plans = _ws(PLANS_SHEET)
    if plans.row_values(1)[:4] != ["Период", "Категория", "План", "Обновлено"]:
        plans.clear()
        plans.insert_row(["Период", "Категория", "План", "Обновлено"], 1)


# ---------- Операции ----------

def append_operation(op_date, category, amount, comment=""):
    """Записать операцию в лист."""
    ws = _ws(OPS_SHEET)
    ws.append_row(
        [op_date.isoformat(), category, float(amount), comment],
        value_input_option="USER_ENTERED",
    )


def get_operations():
    """Список всех операций в виде словарей."""
    rows = _ws(OPS_SHEET).get_all_values()
    result = []
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        try:
            result.append({
                "date": date.fromisoformat(r[0]),
                "category": r[1],
                "amount": float((r[2] or "0").replace(",", ".")),
                "comment": r[3] if len(r) > 3 else "",
            })
        except (ValueError, IndexError):
            continue
    return result


def delete_last_operation():
    """Удалить последнюю строку с операцией. Возвращает удалённое или None."""
    ws = _ws(OPS_SHEET)
    vals = ws.get_all_values()
    if len(vals) <= 1:
        return None
    last = ws.row_values(len(vals))
    ws.delete_rows(len(vals))
    return last


# ---------- Периоды (бюджетный месяц 10-го → 9-го) ----------

def current_period_label(ref_date=None):
    """Возвращает название текущего бюджетного периода.
    Например, для 15.10.2026 вернёт '2026-10'."""
    d = ref_date or date.today()
    if d.day >= BUDGET_START_DAY:
        return f"{d.year:04d}-{d.month:02d}"
    # Если ещё не наступило 10-е — мы в прошлом периоде
    prev = d.replace(day=1) - timedelta(days=1)
    return f"{prev.year:04d}-{prev.month:02d}"


def period_bounds(label):
    """'2026-10' -> (date(2026,10,10), date(2026,11,9))."""
    y, m = map(int, label.split("-"))
    start = date(y, m, BUDGET_START_DAY)
    if m == 12:
        next_y, next_m = y + 1, 1
    else:
        next_y, next_m = y, m + 1
    next_start = date(next_y, next_m, BUDGET_START_DAY)
    end = next_start - timedelta(days=1)
    return start, end


def next_period_label(ref_date=None):
    """Метка следующего периода."""
    d = ref_date or date.today()
    cur_label = current_period_label(d)
    y, m = map(int, cur_label.split("-"))
    if m == 12:
        return f"{y + 1:04d}-01"
    return f"{y:04d}-{m + 1:02d}"


def operations_in_period(label):
    """Все операции, попадающие в бюджетный период."""
    start, end = period_bounds(label)
    return [o for o in get_operations() if start <= o["date"] <= end]


# ---------- Планы ----------

def get_plan(period_label, category):
    """План на период для категории. Если не задан — None."""
    rows = _ws(PLANS_SHEET).get_all_values()
    for r in rows[1:]:
        if len(r) >= 3 and r[0] == period_label and r[1] == category:
            try:
                return float(str(r[2]).replace(",", "."))
            except ValueError:
                return None
    return None


def set_plan(period_label, category, value):
    """Задать план на период. Если уже есть — перезаписать."""
    ws = _ws(PLANS_SHEET)
    rows = ws.get_all_values()
    for i, r in enumerate(rows[1:], start=2):
        if len(r) >= 2 and r[0] == period_label and r[1] == category:
            ws.update(f"C{i}:D{i}",
                      [[float(value), date.today().isoformat()]])
            return
    ws.append_row([period_label, category, float(value),
                   date.today().isoformat()],
                  value_input_option="USER_ENTERED")


def get_all_plans(period_label):
    """Все планы на период в виде {категория: сумма}."""
    rows = _ws(PLANS_SHEET).get_all_values()
    result = {}
    for r in rows[1:]:
        if len(r) >= 3 and r[0] == period_label and r[1]:
            try:
                result[r[1]] = float(str(r[2]).replace(",", "."))
            except ValueError:
                continue
    return result