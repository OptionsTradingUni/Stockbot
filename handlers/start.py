from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

WELCOME = (
    "👋 Welcome to <b>Profit Flex</b>\n\n"
    "What you can do:\n"
    "• 🏆 View live Top Traders\n"
    "• 🌍 Country leaderboards\n"
    "• 📈 Asset leaderboards (Meme/Crypto/Stocks)\n"
    "• 💡 Success stories\n"
    "• 🏅 Hall of Fame (Daily/Weekly/Monthly)\n\n"
    "Pick an option below."
)

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Rankings", callback_data="rankings"),
         InlineKeyboardButton("📈 Asset Leaderboard", callback_data="asset_leaderboard")],
        [InlineKeyboardButton("🌍 Country Leaderboard", callback_data="country_leaderboard"),
         InlineKeyboardButton("🏅 Hall of Fame", callback_data="hall_of_fame")],
        [InlineKeyboardButton("💡 Success Stories", callback_data="stories"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ])

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Always reply privately if possible
    try:
        uid = update.effective_user.id
        await context.bot.send_message(chat_id=uid, text=WELCOME, parse_mode=constants.ParseMode.HTML, reply_markup=main_menu_kb())
    except Exception:
        await update.effective_message.reply_text("Open me in DM and press /start to use the menu.")
