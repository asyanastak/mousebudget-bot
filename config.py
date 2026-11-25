import os
from dotenv import load_dotenv

load_dotenv()

# Секреты из файла .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# Часовой пояс и время напоминаний
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "21"))
REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", "0"))

# День начала бюджетного месяца (у вас — 10-е число)
BUDGET_START_DAY = int(os.getenv("BUDGET_START_DAY", "10"))

# Названия листов в Google-таблице
OPS_SHEET = "Операции"
CATS_SHEET = "Категории"
SUMMARY_SHEET = "Сводка"
PLANS_SHEET = "Планы"

# ID чата для напоминаний
CHAT_ID = os.getenv("CHAT_ID")