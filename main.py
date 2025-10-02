import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers.start import start_handler
# import other handlers here as you build them

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    if TELEGRAM_TOKEN is None:
        raise SystemExit("TELEGRAM_TOKEN not set in .env")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    # app.add_handler(CallbackQueryHandler(...))  <-- add your button handler

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
