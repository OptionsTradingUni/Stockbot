# handlers.py
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes
from db import fetch_cached_rankings, get_success_stories
from data import WEBSITE_URL, RANKING_TRADERS, COUNTRIES

# -----------------------
# Success Stories
# -----------------------
def craft_success_story(current_index: int, gender: str, stories):
    combined = [("male", s) for s in stories["male"]] + [("female", s) for s in stories["female"]]
    total = len(combined)
    current_index = current_index % total
    gender, story_data = combined[current_index]

    story = story_data["story"]
    image_url = story_data["image"]

    keyboard = [
        [InlineKeyboardButton("⬅️ Prev", callback_data=f"success_prev_{gender}_{current_index}")],
        [InlineKeyboardButton("➡️ Next", callback_data=f"success_next_{gender}_{current_index}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    return story, InlineKeyboardMarkup(keyboard), image_url


# -----------------------
# Start Command
# -----------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or user.username or "Trader"

    stories = get_success_stories()
    total_stories = len(stories["male"]) + len(stories["female"])
    random_index = random.randint(0, total_stories - 1)

    keyboard = [
        [InlineKeyboardButton("📊 View Rankings", callback_data="rankings"),
         InlineKeyboardButton("📖 Success Stories", callback_data=f"success_any_{random_index}")],
        [InlineKeyboardButton("🌐 Visit Website", url=WEBSITE_URL)],
        [InlineKeyboardButton("🏆 Hall of Fame", callback_data="hall_of_fame")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 Welcome, <b>{name}</b>!\n\n"
        f"At <b>Options Trading University</b>, we share live-style profit updates, rankings, "
        f"and inspiring success stories from traders worldwide.\n\n"
        f"📈 Features:\n"
        f"- Stock & Crypto profits (2x–8x)\n"
        f"- Meme coin moonshots (5x–50x, rare 100x!)\n"
        f"- Daily / Weekly / Monthly leaderboards\n"
        f"- 🌍 Country-based rankings\n\n"
        f"Tap a button below to explore 👇"
    )

    await context.bot.send_message(
        chat_id=user.id,
        text=welcome_text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )


# -----------------------
# Rankings Command
# -----------------------
async def trade_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = await fetch_cached_rankings()
    greed_fear = random.randint(25, 75)  # realistic range
    mood = "🐂 Bullish" if greed_fear > 60 else "🐻 Bearish" if greed_fear < 40 else "🟡 Neutral"

    msg = (
        f"🏆 <b>Top Trader Rankings</b> 🏆\n"
        f"As of {ts}:\n"
        f"{'\n'.join(lines[:10])}\n\n"
        f"📊 Market Mood: {mood} (Greed/Fear Index: {greed_fear}/100)\n"
        f"Join us at {WEBSITE_URL}! #TradingCommunity"
    )

    keyboard = [
        [InlineKeyboardButton("🌍 Country Leaderboard", callback_data="country_leaderboard"),
         InlineKeyboardButton("📈 ROI Leaderboard", callback_data="roi_leaderboard")],
        [InlineKeyboardButton("📊 Asset Leaderboard", callback_data="asset_leaderboard")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=msg,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# -----------------------
# Help Command
# -----------------------
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ <b>Help & Commands</b> ℹ️\n\n"
        "/start - Open main menu\n"
        "/status - Market status update\n"
        "/trade_status - Rankings overview\n"
        "/hall_of_fame - Top winners archive\n"
        "/help - Show this help menu\n\n"
        "✅ Profit updates auto-post every 20–40 minutes into the group."
    )
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# -----------------------
# Button Handler
# -----------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Success Stories navigation
    if data.startswith("success_any") or data.startswith("success_prev") or data.startswith("success_next"):
        stories = get_success_stories()
        parts = data.split("_")
        idx = int(parts[-1])
        gender = parts[1] if len(parts) > 2 else "male"
        story, reply_markup, image_url = craft_success_story(idx, gender, stories)
        await query.message.reply_photo(photo=image_url, caption=story, reply_markup=reply_markup)

    # Rankings
    elif data == "rankings":
        await trade_status_handler(update, context)

    elif data == "roi_leaderboard":
        await query.message.reply_text("📈 ROI Leaderboard (coming soon!)")

    elif data == "asset_leaderboard":
        await query.message.reply_text("📊 Asset Leaderboard (coming soon!)")

    elif data == "country_leaderboard":
        country = random.choice(list(COUNTRIES.keys()))
        await query.message.reply_text(f"🌍 Top traders in {country} (coming soon!)")

    elif data == "hall_of_fame":
        await query.message.reply_text("🏆 Hall of Fame Winners (coming soon!)")

    elif data == "back":
        await start_handler(update, context)
