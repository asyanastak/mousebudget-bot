import re
from datetime import date, timedelta
from categories import find_category

# Слова-маркеры дат
DATE_WORDS = {
    "сегодня": 0,
    "вчера": 1,
    "позавчера": 2,
}

# "след" или "следующий" — записать в следующий бюджетный месяц
NEXT_MARKERS = ["след", "следующий", "следующее"]

# Дата формата 14.10 или 14.10.2026
DATE_RE = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\b")


def _strip_number_spaces(text):
    """Убирает пробелы внутри чисел: '1 200' -> '1200'."""
    return re.sub(r"(?<=\d)\s+(?=\d)", "", text.strip())


def _parse_date(lower, next_month=False):
    """Определяет дату операции."""
    # Явная дата 14.10 или 14.10.26
    m = DATE_RE.search(lower)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else date.today().year
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d), False
        except ValueError:
            pass

    # Слова "сегодня/вчера/позавчера"
    for word, days in DATE_WORDS.items():
        if re.search(rf"\b{word}\b", lower):
            return date.today() - timedelta(days=days), False

    # "след" — пойдёт в следующий период, ставим заглушку сегодня
    if any(mark in lower for mark in NEXT_MARKERS):
        return date.today(), True

    return date.today(), False


def parse_message(text):
    """
    Разбирает сообщение. Возвращает:
    {
        amount: float,        # сумма
        category: str|None,   # название категории или None, если не угадали
        date: date,           # дата операции
        next_period: bool,    # True, если надо записать в следующий бюджетный месяц
        raw: str,             # очищенный текст (для кнопок и логов)
    }
    или None, если это не похоже на операцию.
    """
    if not text or text.startswith("/"):
        return None

    norm = _strip_number_spaces(text)
    lower = norm.lower()

    # Определяем "след" до того, как вычистим стоп-слова
    next_period = any(mark in lower for mark in NEXT_MARKERS)

    # Дата
    op_date, _ = _parse_date(lower)

    # Сумма — первое число (можно с точкой или запятой)
    m = re.search(r"\d+(?:[.,]\d+)?", norm)
    if not m:
        return None
    try:
        amount = float(m.group().replace(",", "."))
    except ValueError:
        return None
    if amount <= 0:
        return None

    # Всё остальное — потенциальное название категории
    rest = (norm[: m.start()] + " " + norm[m.end():]).lower()

    # Убираем даты и служебные слова
    rest = DATE_RE.sub(" ", rest)
    rest = re.sub(r"\b(сегодня|вчера|позавчера)\b", " ", rest)
    rest = re.sub(r"\b(след|следующий|следующее)\b", " ", rest)
    # Убираем предлоги "на", "за", "для" в начале
    rest = re.sub(r"\s+", " ", rest).strip()
    rest = re.sub(r"^(на|за|для|по)\s+", "", rest)

    category = find_category(rest)

    return {
        "amount": amount,
        "category": category,
        "date": op_date,
        "next_period": next_period,
        "raw": rest or "—",
    }