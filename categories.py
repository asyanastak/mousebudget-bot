# Список категорий вашего семейного бюджета.
# Название -> тип + синонимы.
#
# Типы:
#   income  — доход (зарплата, подработка, подарки)
#   expense — расход
#   debt    — долг (рассрочка)

CATEGORIES = {
    "Зарплата": {
        "type": "income",
        "synonyms": ["зарплата", "зп", "зарплату"],
    },
    "Прочий доход": {
        "type": "income",
        "synonyms": ["фриланс", "подработка", "подарок", "подарили",
                     "премия", "доход", "кэшбэк", "кешбэк"],
    },
    "Аренда квартиры": {
        "type": "expense",
        "synonyms": ["аренда", "за квартиру"],
    },
    "Коммуналка": {
        "type": "expense",
        "synonyms": ["коммуналка", "жкх", "квартплата", "коммунальные"],
    },
    "Продукты": {
        "type": "expense",
        "synonyms": ["продукты", "еда", "в магазин", "супермаркет",
                     "пятёрочка", "пятерочка", "лента", "ашан",
                     "магнит", "перекрёсток"],
    },
    "Еда вне дома": {
        "type": "expense",
        "synonyms": ["еда вне дома", "кафе", "ресторан", "рестик",
                     "доставка", "кофе", "обед", "шаурма", "пицца", "суши"],
    },
    "Здоровье и быт.химия": {
        "type": "expense",
        "synonyms": ["здоровье", "аптека", "врач", "лекарства",
                     "анализы", "стоматолог", "бытовуха", "бытовая химия",
                     "химия", "порошок", "мыло", "быт.химия"],
    },
    "Транспорт": {
        "type": "expense",
        "synonyms": ["транспорт", "такси", "бензин", "метро",
                     "автобус", "каршеринг", "проезд"],
    },
    "Связь интернет": {
        "type": "expense",
        "synonyms": ["связь", "интернет", "мобилка", "мтс", "билайн",
                     "мегафон", "теле2", "сотовый"],
    },
    "Одежда": {
        "type": "expense",
        "synonyms": ["одежда", "шмотки", "обувь"],
    },
    "Прочее": {
        "type": "expense",
        "synonyms": ["прочее", "другое", "разное"],
    },
    "Рассрочка": {
        "type": "debt",
        "synonyms": ["рассрочка", "рассрочку"],
    },
}


def find_category(text):
    """Ищет категорию по тексту сообщения. Возвращает название или None."""
    if not text:
        return None
    text = text.lower()

    # Сначала точное совпадение — если вся строка это один синоним
    for cat, meta in CATEGORIES.items():
        for syn in meta["synonyms"]:
            if text == syn:
                return cat

    # Потом по вхождению, но выбираем самый длинный синоним
    # (чтобы "еда вне дома" нашлось раньше, чем "еда")
    matches = []
    for cat, meta in CATEGORIES.items():
        for syn in meta["synonyms"]:
            if syn in text:
                matches.append((len(syn), cat))
    if matches:
        matches.sort(reverse=True)
        return matches[0][1]
    return None


def get_type(category):
    """Возвращает тип категории: income / expense / debt."""
    if category in CATEGORIES:
        return CATEGORIES[category]["type"]
    return None


ALL_CATEGORY_NAMES = list(CATEGORIES.keys())