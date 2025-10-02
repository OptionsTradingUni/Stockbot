import os
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from handlers import (
    start, status, trade_status, help_command, hall_of_fame,
    success_stories, prev_success, next_success, reaction_callback
)
from utils import post_profit_alert, initialize_data
from db import init_db

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    # Load environment variables
    load_dotenv()
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("No TELEGRAM_BOT_TOKEN found in .env")

    # Initialize database
    init_db()
    initialize_data()

    # Set up Telegram bot
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("trade_status", trade_status))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("hall_of_fame", hall_of_fame))
    
    # Add callback query handlers
    application.add_handler(CallbackQueryHandler(success_stories, pattern="^success_"))
    application.add_handler(CallbackQueryHandler(prev_success, pattern="^prev_success$"))
    application.add_handler(CallbackQueryHandler(next_success, pattern="^next_success$"))
    application.add_handler(CallbackQueryHandler(reaction_callback, pattern="^(fire|rocket|shock)$"))

    # Set up scheduler for autopilot posts
    scheduler = AsyncIOScheduler()
    scheduler.add_job(post_profit_alert, "interval", minutes=5, args=[application.bot])
    scheduler.start()

    # Start bot
    try:
        await application.run_polling()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
