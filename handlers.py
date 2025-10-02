import asyncio, random
from datetime import datetime, timezone, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants, Update
from telegram.ext import ContextTypes
from config import TELEGRAM_CHAT_ID, WEBSITE_URL, STOCK_SYMBOLS, CRYPTO_SYMBOLS, MEME_COINS, ALL_SYMBOLS, RATE_LIMIT_SECONDS, POST_MINUTES, POST_WEIGHTS
from data import RANKING_TRADERS, COUNTRIES
from db import engine, users, trader_metadata, hall_of_fame
from sqlalchemy import select, insert, update
from rankings import get_cached_rankings, maybe_insert_and_refresh, format_rank_lines
from leaderboards import roi_leaderboard, asset_leaderboard, country_leaderboard
from profits import generate_scenario, upsert_trending, log_trade

# ---------- helpers ----------

def _welcome_keyboard(random_index: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Success Stories", callback_data=f"success_any_{random_index}")],
        [InlineKeyboardButton("📢 Join Profit Group", url="https://t.me/+v2cZ4q1DXNdkMjI8")],
        [InlineKeyboardButton("Visit Website", url=WEBSITE_URL),
         InlineKeyboardButton("Terms of Service", callback_data="terms")],
        [InlineKeyboardButton("Privacy Policy", callback_data="privacy"),
         InlineKeyboardButton("Hall of Fame", callback_data="hall_of_fame")]
    ])

def _send_private_or_alert(query, context: ContextTypes.DEFAULT_TYPE, text, reply_markup=None):
    async def _inner():
        try:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=text,
                parse_mode=constants.ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception:
            await query.answer("⚠️ DM the bot first with /start to access.", show_alert=True)
    return _inner()

# Greed/Fear: weighted by last 100 posts win ratio & average ROI magnitude
def compute_greed_fear():
    from sqlalchemy import text as sqltext
    import pandas as pd
    df = pd.read_sql(sqltext("""
        SELECT profit, deposit FROM posts ORDER BY posted_at DESC LIMIT 100
    """), engine)
    if df.empty: 
        return 50, "🟡 Neutral"
    wins = (df['profit'] > 0).mean()  # share of wins
    roi = (df['profit'] / df['deposit']).fillna(0).clip(-1, 5)  # cap extremes
    mean_roi = roi.mean()
    # map to 0..100 with sane weights
    score = int(40 + 40 * wins + 20 * (max(min(mean_roi, 1.5), -0.5) + 0.5))  # center around 50
    score = max(0, min(100, score))
    mood = "🐂 Bullish" if score > 60 else "🐻 Bearish" if score < 40 else "🟡 Neutral"
    return score, mood

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or user.username or "Trader"

    # login streak tracking
    with engine.begin() as conn:
        row = conn.execute(select(users.c.last_login, users.c.login_streak).where(users.c.user_id == str(user.id))).fetchone()
        streak = 1
        if row and row[0]:
            days = (datetime.now(timezone.utc) - row[0].replace(tzinfo=timezone.utc)).days
            streak = (row[1] + 1) if days == 1 else (row[1] if days == 0 else 1)
        conn.execute(insert(users).values(
            user_id=str(user.id), username=user.username or "unknown", display_name=name,
            wins=0, total_trades=0, total_profit=0, last_login=datetime.now(timezone.utc), login_streak=streak
        ).prefix_with("OR IGNORE"))
        conn.execute(update(users).where(users.c.user_id == str(user.id)).values(
            last_login=datetime.now(timezone.utc), login_streak=streak
        ))

    idx = random.randint(0, 9)
    welcome_text = (
        f"👋 Welcome, {name}!\n\n"
        f"Options Trading University:\n"
        f"• Realistic profit drops (stocks/crypto/memes)\n"
        f"• Leaderboards (Overall, ROI, Asset, Country)\n"
        f"• Daily/Weekly/Monthly winners + Hall of Fame\n"
        f"• Greed/Fear that reacts to win-rate & ROI\n\n"
        f"Tap a button to explore. 🚀"
    )
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=welcome_text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=_welcome_keyboard(idx)
    )

# ---------- rankings block text ----------
async def rankings_text():
    pairs = get_cached_rankings()
    lines = format_rank_lines(pairs)
    gf, mood = compute_greed_fear()
    return (
        "🏆 <b>Top Trader Rankings</b>\n" +
        "\n".join(lines) +
        f"\n\n📊 Market Mood: {mood} (Greed/Fear {gf}/100)"
    )

# ---------- callbacks ----------
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "rankings":
        txt = await rankings_text()
        return await _send_private_or_alert(query, context, txt, InlineKeyboardMarkup([
            [InlineKeyboardButton("ROI Leaderboard", callback_data="roi_leaderboard")],
            [InlineKeyboardButton("Asset Leaderboards", callback_data="asset_leaderboard")],
            [InlineKeyboardButton("Country Leaderboards", callback_data="country_leaderboard")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]))

    elif data == "roi_leaderboard":
        lines = roi_leaderboard()
        msg = "📈 <b>Top ROI Leaderboard</b>\n" + ("\n".join(lines) if lines else "No data yet.")
        return await _send_private_or_alert(query, context, msg, InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))

    elif data == "asset_leaderboard":
        return await _send_private_or_alert(query, context,
            "Choose asset type:", InlineKeyboardMarkup([
                [InlineKeyboardButton("Stocks", callback_data="asset_stocks")],
                [InlineKeyboardButton("Crypto", callback_data="asset_crypto")],
                [InlineKeyboardButton("Meme Coins", callback_data="asset_meme")],
                [InlineKeyboardButton("Back", callback_data="back")]
            ]))

    elif data.startswith("asset_"):
        kind = data.split("_")[1]
        if kind == "stocks":
            lines = asset_leaderboard(STOCK_SYMBOLS)
        elif kind == "crypto":
            lines = asset_leaderboard(CRYPTO_SYMBOLS)
        else:
            lines = asset_leaderboard(MEME_COINS)
        msg = f"📊 <b>{kind.capitalize()} Leaderboard</b>\n" + ("\n".join(lines) if lines else "No data.")
        return await _send_private_or_alert(query, context, msg, InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))

    elif data == "country_leaderboard":
        rows = [ [InlineKeyboardButton(c, callback_data=f"country_{c}")] for c in COUNTRIES[:20] ]
        rows.append([InlineKeyboardButton("Back", callback_data="back")])
        return await _send_private_or_alert(query, context, "🌍 Pick a country:", InlineKeyboardMarkup(rows))

    elif data.startswith("country_"):
        country = data.split("_",1)[1]
        lines = country_leaderboard(country)
        msg = f"🌍 <b>{country} Leaderboard</b>\n" + ("\n".join(lines) if lines else "No traders yet.")
        return await _send_private_or_alert(query, context, msg, InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))

    elif data in ("terms","privacy","hall_of_fame","back"):
        if data == "terms":
            text = ("📜 <b>Terms</b>\nUse at your own risk. Info only, not financial advice.")
        elif data == "privacy":
            text = ("🔒 <b>Privacy</b>\nWe store minimal IDs for bot features. We do not sell user data.")
        elif data == "hall_of_fame":
            from sqlalchemy import select
            with engine.connect() as conn:
                rows = conn.execute(select(hall_of_fame.c.trader_name, hall_of_fame.c.profit, hall_of_fame.c.scope, hall_of_fame.c.timestamp)
                                    .order_by(hall_of_fame.c.timestamp.desc()).limit(10)).fetchall()
            lines = [f"🏆 <b>{r[0]}</b> — ${int(r[1]):,} ({r[2].capitalize()}, {r[3].date()})" for r in rows]
            text = "🏛️ <b>Hall of Fame</b>\n" + ("\n".join(lines) if lines else "No winners yet.")
        else:
            idx = random.randint(0,9)
            text = ("📌 <b>Options Trading University</b>\n"
                    "• Realistic profit posts\n• Leaderboards\n• Hall of Fame\n• Private menu")
            return await _send_private_or_alert(query, context, text, _welcome_keyboard(idx))
        return await _send_private_or_alert(query, context, text, InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]]))

# ---------- /status, /help, /trade_status, /hall_of_fame ----------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (f"📈 <b>Market Overview</b>\n"
           f"Stocks: {', '.join(STOCK_SYMBOLS)}\n"
           f"Crypto: {', '.join(CRYPTO_SYMBOLS)}\n"
           f"Memes: {', '.join(MEME_COINS)}\n"
           f"Profit drops come in waves. Stay sharp. 🚀")
    await context.bot.send_message(chat_id=update.effective_user.id, text=txt, parse_mode=constants.ParseMode.HTML,
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("View Rankings", callback_data="rankings")]]))

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = ("ℹ️ <b>Commands</b>\n"
           "/start – open menu (DM)\n"
           "/status – overview\n"
           "/trade_status – rankings\n"
           "/hall_of_fame – winners")
    await context.bot.send_message(chat_id=update.effective_user.id, text=txt, parse_mode=constants.ParseMode.HTML)

async def trade_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = await rankings_text()
    await context.bot.send_message(chat_id=update.effective_user.id, text=txt, parse_mode=constants.ParseMode.HTML)

async def hall_of_fame_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from sqlalchemy import select
    with engine.connect() as conn:
        rows = conn.execute(select(hall_of_fame.c.trader_name, hall_of_fame.c.profit, hall_of_fame.c.scope, hall_of_fame.c.timestamp)
                            .order_by(hall_of_fame.c.timestamp.desc()).limit(10)).fetchall()
    lines = [f"🏆 <b>{r[0]}</b> — ${int(r[1]):,} ({r[2].capitalize()}, {r[3].date()})" for r in rows]
    txt = "🏛️ <b>Hall of Fame</b>\n" + ("\n".join(lines) if lines else "No winners yet.")
    await context.bot.send_message(chat_id=update.effective_user.id, text=txt, parse_mode=constants.ParseMode.HTML)

# ---------- posting loop ----------
async def posting_loop(app):
    from rankings import get_cached_rankings
    while True:
        wait_mins = random.choices(POST_MINUTES, weights=POST_WEIGHTS)[0]
        await asyncio.sleep(wait_mins * 60)

        symbol = random.choice(ALL_SYMBOLS)
        deposit, profit, pct, reason, style, is_loss = generate_scenario(symbol)
        upsert_trending(symbol)

        # craft message (include top 5 snapshot)
        pairs = get_cached_rankings()
        lines = format_rank_lines(pairs)[:5]
        mention_name = random.choice([n for _, n in RANKING_TRADERS])
        hdr = "📉 Loss Update" if is_loss else "📈 Profit Update"
        msg = (f"{hdr} — <b>{symbol}</b>\n"
               f"{style} | Invested: ${deposit:,.0f}\n"
               f"{'Loss' if is_loss else 'Realized'}: ${abs(int(profit)):,}  (ROI {abs(pct)}%{' loss' if is_loss else ''})\n"
               f"{reason}\n\n"
               f"🏆 Top Traders:\n" + "\n".join(lines) + f"\n\n"
               f"Shoutout to {mention_name}!  Join us: {WEBSITE_URL}")

        trader_id, trader_name = random.choice(RANKING_TRADERS)
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode=constants.ParseMode.HTML)

        # persist + maybe bump rankings cache
        log_trade(symbol, msg, deposit, profit, trader_id)
        new_pairs = maybe_insert_and_refresh(trader_name, int(max(0, profit)))
        if new_pairs != pairs and profit > 0:
            # shoutout if entered
            await app.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"🔥 BREAKING: <b>{trader_name}</b> just entered the Top 20 with ${int(profit):,}!",
                parse_mode=constants.ParseMode.HTML
            )

        await asyncio.sleep(RATE_LIMIT_SECONDS)

        # sometimes post recap / polls / winners
        if random.random() < 0.2:
            txt = await rankings_text()
            await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=txt, parse_mode=constants.ParseMode.HTML)

        # winners (low chance per loop)
        if random.random() < 0.05:
            await announce_winner("daily", app)
        if random.random() < 0.02:
            await announce_winner("weekly", app)
        if random.random() < 0.01:
            await announce_winner("monthly", app)

async def announce_winner(scope, app):
    # Take current #1 from cached rankings
    pairs = get_cached_rankings()
    if not pairs:
        return
    winner = pairs[0]
    from db import record_hof_winner
    record_hof_winner(winner["name"], winner["profit"], scope)
    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"👑 <b>{scope.capitalize()} Winner:</b> {winner['name']} — ${winner['profit']:,}",
        parse_mode=constants.ParseMode.HTML
    )
