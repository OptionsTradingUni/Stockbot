import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram import constants

from handlers import (
    start_handler,
    button_handler
)
from db import init_db
from data import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from posting import profit_posting_loop

# -------------------------
# Logging
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# -------------------------
# Bot main
# -------------------------
def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise SystemExit("❌ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing from environment!")

    # Init DB tables
    init_db()

    # Build app
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Startup hook
    async def on_startup(app):
        app.create_task(profit_posting_loop(app))
        logger.info("✅ Profit posting loop scheduled.")

    app.post_init = on_startup

    logger.info("🚀 Bot starting...")
    app.run_polling(allowed_updates=constants.Update.ALL_TYPES)


if __name__ == "__main__":
    main()
