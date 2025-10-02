# handlers.py
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes
from db import fetch_cached_rankings, get_success_stories
from data import WEBSITE_URL, RANKING_TRADERS, COUNTRY_TRADERS
from sqlalchemy import text
from db import engine

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
        f"At <b>Options Trading University</b>, we share live profit updates, "
        f"rankings, and inspiring success stories from traders worldwide.\n\n"
        f"📈 Features:\n"
        f"- Stocks & Crypto (2x–8x)\n"
        f"- Meme coin moonshots (5x–50x, rare 100x!)\n"
        f"- Daily / Weekly / Monthly leaderboards\n"
        f"- 🌍 Country-based rankings\n\n"
        f"Tap below to explore 👇"
    )

    await context.bot.send_message(
        chat_id=user.id,
        text=welcome_text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )


# -----------------------
# Main Rankings
# -----------------------
async def trade_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = await fetch_cached_rankings()
    greed_fear = random.randint(40, 70)  # realistic stable range
    mood = "🐂 Bullish" if greed_fear > 60 else "🐻 Bearish" if greed_fear < 45 else "🟡 Neutral"

    msg = (
        f"🏆 <b>Top Trader Rankings</b>\n"
        f"As of {ts}:\n"
        f"{'\n'.join(lines[:10])}\n\n"
        f"📊 Market Mood: {mood} (Greed/Fear Index: {greed_fear}/100)\n"
        f"Join us at {WEBSITE_URL}!"
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
# ROI Leaderboard
# -----------------------
async def roi_leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with engine.connect() as conn:
        df = conn.execute(text("""
            SELECT trader_id, SUM(profit) as total_profit, SUM(deposit) as total_deposit
            FROM posts
            WHERE profit > 0
            GROUP BY trader_id
            HAVING SUM(deposit) > 0
            ORDER BY (SUM(profit)/SUM(deposit)) DESC
            LIMIT 10
        """)).fetchall()

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for i, row in enumerate(df, start=1):
        name = next((n for tid, n in RANKING_TRADERS if tid == row.trader_id), row.trader_id)
        roi = round((row.total_profit / row.total_deposit) * 100, 1)
        badge = medals.get(i, f"{i}.")
        lines.append(f"{badge} {name} — {roi}% ROI (${int(row.total_profit):,})")

    msg = "📈 <b>ROI Leaderboard</b>\n\n" + "\n".join(lines)
    await context.bot.send_message(update.effective_user.id, msg, parse_mode=constants.ParseMode.HTML)


# -----------------------
# Asset Leaderboard
# -----------------------
async def asset_leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbols_groups = {
        "Meme Coins": ["NIKY"],
        "Crypto": ["BTC", "ETH", "SOL"],
        "Stocks": ["TSLA", "AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META"]
    }
    msg = "📊 <b>Asset Leaderboards</b>\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    with engine.connect() as conn:
        for group_name, symbols in symbols_groups.items():
            df = conn.execute(text(f"""
                SELECT trader_id, SUM(profit) as total_profit
                FROM posts
                WHERE symbol IN ({','.join([f"'{s}'" for s in symbols])})
                GROUP BY trader_id
                ORDER BY total_profit DESC
                LIMIT 3
            """)).fetchall()

            msg += f"<b>{group_name}</b>:\n"
            for i, row in enumerate(df, start=1):
                name = next((n for tid, n in RANKING_TRADERS if tid == row.trader_id), row.trader_id)
                badge = medals.get(i, f"{i}.")
                msg += f"{badge} {name} — ${int(row.total_profit):,}\n"
            msg += "\n"

    await context.bot.send_message(update.effective_user.id, msg, parse_mode=constants.ParseMode.HTML)


# -----------------------
# Country Leaderboard
# -----------------------
async def country_leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country = random.choice(list(COUNTRY_TRADERS.keys()))
    trader_ids = COUNTRY_TRADERS[country]

    with engine.connect() as conn:
        df = conn.execute(text(f"""
            SELECT trader_id, SUM(profit) as total_profit
            FROM posts
            WHERE trader_id IN ({','.join([f"'{t}'" for t in trader_ids])})
            GROUP BY trader_id
            ORDER BY total_profit DESC
            LIMIT 5
        """)).fetchall()

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [f"🌍 <b>Top Traders in {country}</b>\n"]
    for i, row in enumerate(df, start=1):
        name = next((n for tid, n in RANKING_TRADERS if tid == row.trader_id), row.trader_id)
        badge = medals.get(i, f"{i}.")
        lines.append(f"{badge} {name} — ${int(row.total_profit):,}")

    msg = "\n".join(lines)
    await context.bot.send_message(update.effective_user.id, msg, parse_mode=constants.ParseMode.HTML)


# -----------------------
# Hall of Fame
# -----------------------
async def hall_of_fame_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with engine.connect() as conn:
        df = conn.execute(text("""
            SELECT trader_name, profit, scope, timestamp
            FROM hall_of_fame
            ORDER BY timestamp DESC
            LIMIT 5
        """)).fetchall()

    if not df:
        msg = "🏆 No Hall of Fame entries yet!"
    else:
        msg = "🏆 <b>Hall of Fame Winners</b>\n\n"
        for row in df:
            msg += f"👑 {row.trader_name} — ${int(row.profit):,} ({row.scope}, {row.timestamp.date()})\n"

    await context.bot.send_message(update.effective_user.id, msg, parse_mode=constants.ParseMode.HTML)


# -----------------------
# Help
# -----------------------
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ <b>Help & Commands</b>\n\n"
        "/start - Main menu\n"
        "/status - Market status\n"
        "/trade_status - Rankings\n"
        "/hall_of_fame - Hall of Fame\n"
        "/help - Show help\n\n"
        "✅ Profit updates post every 20–40 minutes in the group."
    )
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
    await context.bot.send_message(update.effective_user.id, text, parse_mode=constants.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))


# -----------------------
# Button Handler
# -----------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    stories = get_success_stories()

    if data.startswith("success_any") or data.startswith("success_prev") or data.startswith("success_next"):
        parts = data.split("_")
        idx = int(parts[-1])
        gender = parts[1] if len(parts) > 2 else "male"
        story, reply_markup, image_url = craft_success_story(idx, gender, stories)
        await query.message.reply_photo(photo=image_url, caption=story, reply_markup=reply_markup)

    elif data == "rankings":
        await trade_status_handler(update, context)
    elif data == "roi_leaderboard":
        await roi_leaderboard_handler(update, context)
    elif data == "asset_leaderboard":
        await asset_leaderboard_handler(update, context)
    elif data == "country_leaderboard":
        await country_leaderboard_handler(update, context)
    elif data == "hall_of_fame":
        await hall_of_fame_handler(update, context)
    elif data == "back":
        await start_handler(update, context)
