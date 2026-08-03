"""
Telegram bot entrypoint.

Why Telegram first (not WhatsApp directly)?
- Telegram Bot API is 100% free and takes 2 minutes to set up (just @BotFather).
- WhatsApp requires Meta Business verification or a paid provider like Twilio.
- Same LLM + booking logic works for both — see README "Porting to WhatsApp"
  section to swap this file for a Twilio webhook with near-zero logic changes.
"""
import os
import logging
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from knowledge import load_config, build_context
from llm import ask_llm
from booking import start_booking, is_booking_in_progress, handle_booking_step

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
config = load_config()
business_context = build_context(config)

# Keep last few turns per chat so the LLM has short-term memory of the conversation
_chat_history: dict[int, list[dict]] = defaultdict(list)
MAX_HISTORY_TURNS = 6  # 3 user + 3 assistant messages


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    biz_name = config["business"]["name"]
    await update.message.reply_text(
        f"👋 Welcome to {biz_name}!\n\n"
        f"Ask me anything about our services, hours, or location.\n"
        f"Type 'book' anytime to schedule an appointment."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Route to booking flow if one is active, or if user typed "book"
    if is_booking_in_progress(chat_id):
        reply = handle_booking_step(chat_id, text, config)
        await update.message.reply_text(reply)
        return

    if text.lower() in ("book", "book appointment", "appointment"):
        reply = start_booking(chat_id)
        await update.message.reply_text(reply)
        return

    # Otherwise, answer with the LLM grounded on business info
    history = _chat_history[chat_id][-MAX_HISTORY_TURNS:]
    reply = ask_llm(text, business_context, history)

    _chat_history[chat_id].append({"role": "user", "content": text})
    _chat_history[chat_id].append({"role": "assistant", "content": reply})

    await update.message.reply_text(reply)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN not set. Create a bot via @BotFather on Telegram, "
            "then put the token in your .env file."
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting... business: %s", config["business"]["name"])
    app.run_polling()


if __name__ == "__main__":
    main()
