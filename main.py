import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from handlers.start import start_handler
from handlers.buttons import button_handler
from handlers.status import status_handler
from handlers.help import help_handler
from handlers.hof import hall_of_fame_handler
from utils.profits import posting_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("profit-flex")

def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN missing in .env")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("hall_of_fame", hall_of_fame_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    async def _on_startup(_app):
        # start background posting loop
        asyncio.create_task(posting_loop(_app))
        logger.info("Background posting loop started.")

    app.post_init = _on_startup

    logger.info("Bot starting…")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
