from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

async def rankings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Example fake top 5 (replace later with DB integration)
    rankings = [
        "🥇 Robert Garcia — $25,400 profit (Pro, USA)",
        "🥈 Olivia Hernandez — $19,850 profit (Pro, Mexico)",
        "🥉 James Lopez — $17,600 profit (Rookie, UK)",
        "4. Sophia Gonzalez — $15,200 profit (Rookie, Nigeria)",
        "5. William Rodriguez — $13,750 profit (Pro, Brazil)",
    ]
    msg = "🏆 Current Rankings 🏆\n\n" + "\n".join(rankings)

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
    await update.callback_query.message.reply_text(
        msg,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
