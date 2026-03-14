# 💡 Idea Bot — TG → Claude → Notion

Telegram-бот для швидкої фіксації продуктових ідей.

## Як запустити

### 1. Створити Telegram бота
1. Відкрий [@BotFather](https://t.me/BotFather)
2. `/newbot` → дай назву → отримай `TELEGRAM_BOT_TOKEN`

### 2. Notion Integration Token
1. Зайди на https://www.notion.so/my-integrations
2. Створи нову інтеграцію → скопіюй `NOTION_TOKEN`
3. Відкрий свою базу Product Experiments → `...` → Connections → додай свою інтеграцію

### 3. Знайти свій Telegram User ID
Напиши [@userinfobot](https://t.me/userinfobot) — він поверне твій ID.

### 4. Deploy на Railway

1. Створи акаунт на [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo (або завантаж файли вручну)
3. Додай змінні оточення:

| Variable | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен від BotFather |
| `ANTHROPIC_API_KEY` | ключ з console.anthropic.com |
| `NOTION_TOKEN` | токен інтеграції |
| `NOTION_DATABASE_ID` | `2e3fe0c4-a15b-8054-a329-000b8d85ebd4` |
| `ALLOWED_USER_ID` | твій Telegram ID (щоб бот відповідав тільки тобі) |

4. Railway автоматично підхопить `Procfile` і запустить `python bot.py`

### 5. Deploy на Render (альтернатива)

1. Зайди на [render.com](https://render.com) → New → Web Service
2. Підключи GitHub репо
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python bot.py`
5. Додай ті самі env variables

## Як користуватися

1. Напиши будь-яку сиру ідею в чат боту
2. Бот структурує її через Claude і покаже превʼю
3. Обери бренд (MMA або Sequel)
4. Ідея зберігається в Notion зі статусом `Backlog`

## Структура Notion запису

| Поле | Заповнює |
|---|---|
| Short Name | Claude |
| IF...THEN...BECAUSE | Claude |
| Category | Claude |
| Priority | Claude |
| Focus | Claude |
| Brand | Ти (через кнопки) |
| Notes & Details | Claude |
| Status | Автоматично: Backlog |
