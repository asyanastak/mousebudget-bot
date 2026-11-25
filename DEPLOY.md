# Деплой бота (бесплатно)

## Почему перестал работать на PythonAnywhere (free)
На бесплатном PythonAnywhere исходящий трафик ограничен белым списком хостов,
и `api.telegram.org` туда не входит. Прокси на free-тарифе тоже нельзя.
Решение: перенести на хостинг с полным исходящим доступом.

## Вариант 1 — Render.com (рекомендуется, бесплатно)
1. Зарегистрируйтесь на https://render.com (через GitHub).
2. Создайте репозиторий на GitHub и загрузите туда папку `budget-bot`
   (без `.venv/` и `__pycache__/`). Важно: добавьте `.env` в `.gitignore`,
   а секреты задайте в Render → Environment.
3. На Render: New → Background Worker → подключить репозиторий.
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Plan: Free
4. В Environment добавьте переменные из `.env`:
   BOT_TOKEN, SPREADSHEET_ID, GOOGLE_CREDENTIALS_FILE, TIMEZONE,
   REMINDER_HOUR, REMINDER_MINUTE, BUDGET_START_DAY, CHAT_ID.
   Файл `credentials.json` (Google service account) загрузите как Secret File
   с именем `credentials.json` (или вставьте JSON в переменную и поправьте
   config.py, чтобы читать из env).
5. Deploy. Логи смотрите в Dashboard → Logs.

## Вариант 2 — Fly.io (тоже бесплатно, нужна карта для верификации)
   fly launch --no-deploy, fly secrets set ..., fly deploy

## Важно
- Не запускайте бота одновременно в двух местах — будет 409 Conflict.
- На Render free worker «засыпает» при неактивности? Для worker-типа — нет,
  он работает постоянно (но может перезапускаться раз в сутки).
- Google Sheets: убедитесь, что service account имеет доступ к таблице
  (Share → email из credentials.json, роль Editor).

## Мини-приложение (Telegram Web App) — опционально
Если захотите красивый интерфейс для вас с мужем: фронтенд на GitHub Pages /
Cloudflare Pages (бесплатно), бэкенд — тот же Render free или Google Apps Script.
Обращайтесь — сделаю.
