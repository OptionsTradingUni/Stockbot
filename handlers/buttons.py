from telegram import Update
from telegram.ext import ContextTypes
from handlers.rankings import rankings_handler
from handlers.start import start_handler

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "rankings":
        await rankings_handler(update, context)
    elif data == "back":
        await start_handler(update, context)
    else:
        await query.answer("Feature coming soon 🚀")
