import os
import json
import logging
import anthropic
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── ENV ──────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = os.environ.get(
    "NOTION_DATABASE_ID", "2e3fe0c4-a15b-8054-a329-000b8d85ebd4"
)
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))  # залишити 0 = всі

# ── NOTION SCHEMA (для Claude) ────────────────────────────────────────────────
NOTION_SCHEMA = """
Ти PM-асистент. Тобі надходить сира ідея для продуктового експерименту.
Твоє завдання — структурувати її у JSON для Notion бази даних.

Поля Notion (повертай ТІЛЬКИ валідний JSON, без markdown):
{
  "short_name": "Коротка назва (2-5 слів, PascalCase або Title Case)",
  "if_then_because": "IF [зміна] THEN [очікуваний результат] BECAUSE [гіпотеза чому]",
  "category": "одне з: Premium Flow | Activity | Cancel Flow | Feature | Paywall | Review",
  "priority": "одне з: High | Medium | Low",
  "focus": ["масив з: Churn Rate | C0 | LTV | Reputation — вибери 1-2 найрелевантніших"],
  "notes": "Розгорнуті деталі ідеї, контекст, що може бути корисним для розробника або дизайнера"
}

Правила:
- if_then_because ЗАВЖДИ у форматі "IF ... THEN ... BECAUSE ..."
- category і priority — завжди одне значення, точно зі списку
- focus — масив, можна 1-2 елементи
- short_name — лаконічна назва, яку легко запам'ятати
- notes — розгорнуто, зберегти суть ідеї автора
"""

# ── СТАН ─────────────────────────────────────────────────────────────────────
# pending_ideas[user_id] = {"structured": {...}, "brand": None}
pending_ideas: dict[int, dict] = {}


# ── CLAUDE ────────────────────────────────────────────────────────────────────
def structure_idea_with_claude(raw_idea: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": f"{NOTION_SCHEMA}\n\nСира ідея:\n{raw_idea}",
            }
        ],
    )
    raw = message.content[0].text.strip()
    # Прибираємо можливі ```json ... ``` огортки
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ── NOTION ────────────────────────────────────────────────────────────────────
def create_notion_page(structured: dict, brand: str) -> str:
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    focus_options = [{"name": f} for f in structured.get("focus", [])]

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Short Name": {
                "title": [{"text": {"content": structured["short_name"]}}]
            },
            "IF...THEN...BECAUSE": {
                "rich_text": [{"text": {"content": structured["if_then_because"]}}]
            },
            "Category": {"select": {"name": structured["category"]}},
            "Priority": {"select": {"name": structured["priority"]}},
            "Focus": {"multi_select": focus_options},
            "Brand": {"multi_select": [{"name": brand}]},
            "Notes & Details": {
                "rich_text": [{"text": {"content": structured.get("notes", "")}}]
            },
            "Status": {"status": {"name": "Backlog"}},
        },
    }

    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    page_id = resp.json()["id"].replace("-", "")
    return f"https://www.notion.so/{page_id}"


# ── HANDLERS ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт! Надсилай сирі ідеї для продукту — я їх структурую і збережу в Notion.\n\n"
        "Просто напиши ідею будь-якими словами 🧠"
    )


async def handle_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if ALLOWED_USER_ID != 0 and user_id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Немає доступу.")
        return

    raw_idea = update.message.text.strip()
    if len(raw_idea) < 10:
        await update.message.reply_text("Напиши трохи більше про ідею 🙏")
        return

    processing_msg = await update.message.reply_text("🧠 Обробляю ідею...")

    try:
        structured = structure_idea_with_claude(raw_idea)
    except Exception as e:
        logger.error(f"Claude error: {e}")
        await processing_msg.edit_text(f"❌ Помилка Claude: {e}")
        return

    # Зберігаємо структуровану ідею в стані
    pending_ideas[user_id] = {"structured": structured, "raw": raw_idea}

    # Показуємо превʼю і питаємо бренд
    preview = (
        f"✅ *Ось що я зрозумів:*\n\n"
        f"📌 *Назва:* {structured['short_name']}\n"
        f"🔬 *IF→THEN→BECAUSE:*\n_{structured['if_then_because']}_\n"
        f"🏷 *Категорія:* {structured['category']}\n"
        f"⚡ *Пріоритет:* {structured['priority']}\n"
        f"🎯 *Фокус:* {', '.join(structured.get('focus', []))}\n\n"
        f"Для якого бренду?"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("MMA", callback_data="brand:MMA"),
                InlineKeyboardButton("Sequel", callback_data="brand:Sequel"),
            ],
            [InlineKeyboardButton("❌ Скасувати", callback_data="brand:cancel")],
        ]
    )

    await processing_msg.edit_text(preview, parse_mode="Markdown", reply_markup=keyboard)


async def handle_brand_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "brand:cancel":
        pending_ideas.pop(user_id, None)
        await query.edit_message_text("❌ Скасовано. Ідея не збережена.")
        return

    brand = data.split(":")[1]
    idea_data = pending_ideas.get(user_id)

    if not idea_data:
        await query.edit_message_text("⚠️ Ідея не знайдена. Спробуй ще раз.")
        return

    await query.edit_message_text(f"💾 Зберігаю в Notion як *{brand}*...", parse_mode="Markdown")

    try:
        notion_url = create_notion_page(idea_data["structured"], brand)
        pending_ideas.pop(user_id, None)

        structured = idea_data["structured"]
        success_msg = (
            f"✅ *Збережено в Notion!*\n\n"
            f"📌 *{structured['short_name']}* — _{structured['category']}_ | {structured['priority']}\n"
            f"🏷 Бренд: *{brand}*\n\n"
            f"🔗 [Відкрити в Notion]({notion_url})"
        )
        await query.edit_message_text(success_msg, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Notion error: {e}")
        await query.edit_message_text(f"❌ Помилка Notion:\n`{e}`", parse_mode="Markdown")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_brand_callback, pattern="^brand:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_idea))
    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
