# main.py
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv
import os

# Import handlers
from handlers import (
    start_handler,
    status_handler,
    help_handler,
    trade_status_handler,
    hall_of_fame_handler,
    button_handler,
)

# Import posting loop
from posting import profit_posting_loop

# Load environment
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    if TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None:
        raise SystemExit("❌ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in .env")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("trade_status", trade_status_handler))
    app.add_handler(CommandHandler("hall_of_fame", hall_of_fame_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Startup task
    async def on_startup(app):
        app.create_task(profit_posting_loop(app))
        logger.info("✅ Profit posting task started.")

    app.post_init = on_startup

    logger.info("🚀 Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
