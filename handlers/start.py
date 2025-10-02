from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🏆 View Rankings", callback_data="rankings")],
        [InlineKeyboardButton("🌍 Country Leaderboard", callback_data="country_leaderboard")],
        [InlineKeyboardButton("📈 Asset Leaderboard", callback_data="asset_leaderboard")],
        [InlineKeyboardButton("💡 Success Stories", callback_data="success_stories")],
        [InlineKeyboardButton("🏅 Hall of Fame", callback_data="hall_of_fame")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome = (
        "🚀 Welcome to *Profit Flex Bot* 🚀\n\n"
        "Explore:\n"
        "🏆 Top trader rankings\n"
        "🌍 Country-based leaders\n"
        "📈 Asset performance (Meme, Crypto, Stocks)\n"
        "💡 Success stories\n"
        "🏅 Hall of Fame (Daily/Weekly/Monthly winners)\n\n"
        "Choose an option below 👇"
    )

    await update.message.reply_text(
        welcome,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
