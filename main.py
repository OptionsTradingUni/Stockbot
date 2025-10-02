import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from db import create_all, init_traders_if_needed
from stories import initialize_stories
from handlers import start, status, help as help_cmd, trade_status, hall_of_fame_cmd, callbacks, posting_loop

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("profit_flex")

def bootstrap():
    create_all()
    init_traders_if_needed()
    initialize_stories()

async def on_startup(app):
    app.create_task(posting_loop(app))
    logger.info("Posting loop launched.")

def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN not set.")
    bootstrap()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("trade_status", trade_status))
    app.add_handler(CommandHandler("hall_of_fame", hall_of_fame_cmd))
    app.add_handler(CallbackQueryHandler(callbacks))

    app.post_init = on_startup
    logger.info("Bot is starting…")
    app.run_polling()

if __name__ == "__main__":
    main()
