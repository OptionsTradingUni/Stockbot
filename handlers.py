import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

from data import RANKING_TRADERS, COUNTRIES, ALL_TRADERS, WEBSITE_URL
from rankings import fetch_cached_rankings, build_country_leaderboard, build_roi_leaderboard

# -------------------------
# START HANDLER
# -------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🏆 View Rankings", callback_data="rankings")],
        [InlineKeyboardButton("🌍 Country Leaderboards", callback_data="country_leaderboard")],
        [InlineKeyboardButton("📊 ROI Leaderboard", callback_data="roi_leaderboard")],
        [InlineKeyboardButton("📖 Success Stories", callback_data="success_stories")],
        [InlineKeyboardButton("🌐 Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        "🚀 Welcome to **Profit Flex Bot**!\n\n"
        "Here you can:\n"
        "• View live trader rankings 🏆\n"
        "• Check country-specific leaderboards 🌍\n"
        "• Explore ROI champions 📊\n"
        "• Read success stories 📖\n\n"
        "📈 Stay tuned for daily profit updates and market recaps!"
    )

    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    elif update.callback_query:
        await update.callback_query.message.edit_text(msg, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)


# -------------------------
# BUTTON HANDLER
# -------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # Main Rankings
    if data == "rankings":
        lines = await fetch_cached_rankings()
        text = "🏆 **Top Trader Rankings** 🏆\n\n" + "\n".join(lines[:10])
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.MARKDOWN)

    # Country Leaderboards
    elif data == "country_leaderboard":
        # Show a menu of countries
        keyboard = [[InlineKeyboardButton(c, callback_data=f"country_{c}")] for c in COUNTRIES]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
        await query.message.edit_text("🌍 Select a country to view its leaderboard:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("country_"):
        country = data.split("_", 1)[1]
        lines = build_country_leaderboard(country)
        text = f"🌍 **{country} Leaderboard** 🌍\n\n" + "\n".join(lines) if lines else f"No traders found for {country}."
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="country_leaderboard")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.MARKDOWN)

    # ROI Leaderboard
    elif data == "roi_leaderboard":
        lines = build_roi_leaderboard()
        text = "📊 **ROI Leaderboard** 📊\n\n" + "\n".join(lines)
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.MARKDOWN)

    # Success Stories
    elif data == "success_stories":
        story, markup, _ = craft_success_story(0, "male")  # default first story
        await query.message.edit_text(story, reply_markup=markup)

    elif data.startswith("success_prev_") or data.startswith("success_next_"):
        parts = data.split("_")
        action, gender, idx = parts[1], parts[2], int(parts[3])
        idx = idx - 1 if action == "prev" else idx + 1
        story, markup, _ = craft_success_story(idx, gender)
        await query.message.edit_text(story, reply_markup=markup)

    # Back to main menu
    elif data == "back":
        await start_handler(update, context)


# -------------------------
# SUCCESS STORY HELPER
# -------------------------
def craft_success_story(index, gender):
    stories = [
        ("John Doe", "transformed $500 into $5,000 with Tesla scalping 🚀"),
        ("Jane Smith", "turned $700 into $3,200 trading Ethereum 💎"),
        ("Robert Garcia", "made $1,000 → $7,500 flipping $NIKY 🔥"),
        ("Emily Davis", "grew $1,200 into $9,000 with swing trading on BTC 📈"),
    ]
    total = len(stories)
    index = index % total
    story_text = f"📖 Success Story\n\n{stories[index][0]} {stories[index][1]}"

    keyboard = [
        [InlineKeyboardButton("⬅️ Prev", callback_data=f"success_prev_{gender}_{index}")],
        [InlineKeyboardButton("➡️ Next", callback_data=f"success_next_{gender}_{index}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]

    return story_text, InlineKeyboardMarkup(keyboard), None
