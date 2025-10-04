"""
Profit Flex Bot - Real-Time Trading Insights
Delivers authentic profit scenarios for stocks, crypto, and meme coins every 20-40 minutes.
- Stocks/Crypto: Realistic gains (10%-200%).
- Meme Coins: Higher gains (100%-900%).
Powered by a community of winning traders with real names.
Includes success stories and mentions for engagement.
"""




import os
import random
import asyncio
import logging
from sqlalchemy import text
from sqlalchemy import select, delete, insert
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import select, delete, insert, update, text
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
import io
import matplotlib
matplotlib.use("Agg")  # headless backend for servers
import matplotlib.pyplot as plt
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from traders import RANKING_TRADERS

# ✅ Track last posted category (so posts rotate properly)
last_category = None

# ---- Uniqueness tracking (cooldowns) ----
used_deposits: dict[int, float] = {}  # value -> last_used_timestamp
used_profits: dict[int, float] = {}   # value -> last_used_timestamp

DEPOSIT_TTL_SECONDS = 6 * 60 * 60     # 6 hours
PROFIT_TTL_SECONDS  = 12 * 60 * 60    # 12 hours

def _prune_used(used_dict: dict[int, float], ttl_seconds: int) -> None:
    """Remove entries older than ttl_seconds."""
    now = datetime.now().timestamp()
    stale = [v for v, ts in used_dict.items() if (now - ts) > ttl_seconds]
    for v in stale:
        used_dict.pop(v, None)

def _unique_deposit(min_val: int, max_val: int) -> int:
    """
    Return a deposit that hasn't been used recently.
    No rounding — leaves 'organic' numbers like 817, 1045, etc.
    """
    _prune_used(used_deposits, DEPOSIT_TTL_SECONDS)
    now = datetime.now().timestamp()

    # Try a bunch of times to get a fresh one
    for _ in range(200):
        dep = random.randint(min_val, max_val)
        if dep not in used_deposits:
            used_deposits[dep] = now
            return dep

    # Fallback: allow reuse of the least-recently used value
    oldest_val = min(used_deposits.items(), key=lambda x: x[1])[0]
    used_deposits[oldest_val] = now
    return oldest_val

def _unique_profit(candidate_fn) -> int:
    """
    Generate a profit that isn't in recent DB rows or recent cooldown.
    Rounds to the nearest 50 to look realistic.
    """
    _prune_used(used_profits, PROFIT_TTL_SECONDS)
    now = datetime.now().timestamp()
    recent = fetch_recent_profits()  # your existing DB helper

    for _ in range(500):
        raw = candidate_fn()
        prof = int(raw // 50 * 50)
        if prof not in recent and prof not in used_profits:
            used_profits[prof] = now
            return prof

    # Fallback: reuse the least-recently used profit
    if used_profits:
        oldest_val = min(used_profits.items(), key=lambda x: x[1])[0]
        used_profits[oldest_val] = now
        return oldest_val

    # Last resort if everything else failed
    return int(candidate_fn() // 50 * 50)

# Setup logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "profit_flex_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STOCK_SYMBOLS = [s.strip() for s in os.getenv("STOCK_SYMBOLS", "TSLA,AAPL,NVDA,MSFT,AMZN,GOOGL,META").split(",")]
CRYPTO_SYMBOLS = [s.strip() for s in os.getenv("CRYPTO_SYMBOLS", "BTC,ETH,SOL").split(",")]
MEME_COINS = [s.strip() for s in os.getenv("MEME_COINS", "NIKY").split(",")]
ALL_SYMBOLS = STOCK_SYMBOLS + CRYPTO_SYMBOLS + MEME_COINS
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///profit_flex.db")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://optionstradinguni.online/")
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "5"))
IMAGE_DIR = os.getenv("IMAGE_DIR", "images/")

# Init DB
engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

posts = Table(
    "posts", metadata,
    Column("id", Integer, primary_key=True),
    Column("symbol", String),
    Column("content", String),
    Column("deposit", Float),
    Column("profit", Float),
    Column("posted_at", DateTime)
)

users = Table(
    "users", metadata,
    Column("user_id", String, primary_key=True),
    Column("username", String),
    Column("display_name", String),
    Column("wins", Integer),
    Column("total_trades", Integer),
    Column("total_profit", Float, default=0)
)

success_stories = Table(
    "success_stories", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_name", String, unique=True),
    Column("gender", String),
    Column("story", String),
    Column("image", String)
)

# Rankings cache table
rankings_cache = Table(
    "rankings_cache", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("content", String),
    Column("timestamp", DateTime)
)

metadata.create_all(engine)

# -------------------------
# RESET FUNCTION
# -------------------------

def reset_database():
    """
    Full reset:
    - Drops entire public schema in Postgres
    - Recreates tables from metadata
    - Clears posts, users, stories, rankings
    - Seeds a fresh Top 10 leaderboard
    """
    with engine.begin() as conn:
        # Drop and recreate schema
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))

    # Recreate schema
    metadata.create_all(engine)

    # Clear everything just in case
    with engine.begin() as conn:
        conn.execute(delete(posts))
        conn.execute(delete(users))
        conn.execute(delete(success_stories))
        conn.execute(delete(rankings_cache))

    # ✅ Seed new leaderboard with random traders
    selected = random.sample(RANKING_TRADERS, 10)
    initial_board = [(name, random.randint(2000, 10000)) for _, name in selected]
    save_rankings(initial_board)

    logger.info("✅ FULL reset: schema dropped, tables recreated, all cleared, leaderboard reseeded.")
    # Recreate schema
    metadata.create_all(engine)

    # Clear everything just in case
    with engine.begin() as conn:
        conn.execute(delete(posts))
        conn.execute(delete(users))
        conn.execute(delete(success_stories))
        conn.execute(delete(rankings_cache))

    # ✅ Seed new leaderboard
    selected = random.sample(RANKING_TRADERS, 10)
    initial_board = [(name, random.randint(2000, 10000)) for _, name in selected]
    save_rankings(initial_board)

    logger.info("✅ FULL reset: schema dropped, tables recreated, all cleared, leaderboard reseeded.")


# -------------------------
# /resetdb handler
# -------------------------

async def resetdb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    # 🔐 Restrict to admin only
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("🚫 You are not authorized to reset the database.")
        return

    try:
        reset_database()
        await update.message.reply_text("✅ Database has been reset, schema recreated, and leaderboard reseeded.")

        # DM admin confirmation
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="⚡️ DB Reset completed successfully → Top 10 traders reseeded."
            )
    except Exception as e:
        err = f"❌ Reset failed: {e}"
        logger.error(err)
        await update.message.reply_text(err)
        if ADMIN_ID:
            await context.bot.send_message(chat_id=ADMIN_ID, text=err)

    

    # Recreate tables
    metadata.create_all(engine)

    # Optional reseed
    init_traders_if_needed()
    initialize_posts()

    logger.info("✅ FULL Database reset and reseeded.")

    # Recreate all tables defined in metadata
    metadata.create_all(engine)

    # Seed sample data
    init_traders_if_needed()
    initialize_posts()

    logger.info("✅ FULL Database reset, schema recreated, and re-seeded.")

# Bot instance
bot = Bot(token=TELEGRAM_TOKEN)

SUCCESS_TRADERS = {
    "male": [
        ("JohnDoeTrader", "John Doe", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male1.jpeg"),
        ("AlexJohnson", "Alex Johnson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male2.jpeg"),
        ("MichaelBrown", "Michael Brown", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male3.jpeg"),
        ("DavidMiller", "David Miller", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male4.jpeg"),
        ("ChrisAnderson", "Chris Anderson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male5.jpeg")
    ],
    "female": [
        ("JaneSmithPro", "Jane Smith", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female1.jpeg"),
        ("EmilyDavis", "Emily Davis", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female2.jpeg"),
        ("SarahWilson", "Sarah Wilson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female3.jpeg"),
        ("LauraTaylor", "Laura Taylor", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female4.jpeg"),
        ("AnnaMartinez", "Anna Martinez", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female5.jpeg")
    ]
}

# Story templates
SUCCESS_STORY_TEMPLATES = {
    "male": [
        "transformed a modest ${deposit} investment into an impressive ${profit} through a meticulously planned swing trade on AAPL.",
        "turned ${deposit} into a remarkable ${profit} by mastering the art of BTC HODL.",
        "flipped a ${deposit} stake into ${profit} with a bold NIKY pump riding move.",
        "achieved a stunning ${profit} profit from a strategic ETH DCA plan starting with ${deposit}.",
        "earned ${profit} through a clever SOL arbitrage play after investing ${deposit}."
    ],
    "female": [
        "grew a ${deposit} investment into ${profit} with a disciplined TSLA scalping strategy.",
        "boosted ${deposit} into ${profit} with an early sniping move on DOGE.",
        "turned ${deposit} into ${profit} via a SHIB community flip.",
        "made ${profit} from a NVDA position trade starting with ${deposit}.",
        "grew ${deposit} into ${profit} with a GOOGL day trading plan."
    ]
}

def initialize_stories():
    with engine.begin() as conn:
        existing = conn.execute(success_stories.select()).fetchall()
        if existing:
            logger.info("Loaded success stories from DB.")
            stories = {"male": [], "female": []}
            for row in existing:
                stories[row.gender].append({
                    "name": row.trader_name,
                    "story": row.story,
                    "image": row.image  # already a URL now
                })
            return stories

        logger.info("Generating new success stories...")
        stories = {"male": [], "female": []}

        deposits = [300, 400, 500, 600, 700, 800, 1000, 1200, 1500, 2000]
        random.shuffle(deposits)  

        profits_used = set()

        for gender, traders in SUCCESS_TRADERS.items():
            for _, name, image_url in traders:  # now we use URL directly
                deposit = deposits.pop()

                # Generate realistic profits
                profit = None
                while not profit or profit in profits_used:
                    raw_profit = deposit * random.uniform(2, 8)
                    round_base = random.choice([50, 100])  
                    profit = int(round(raw_profit / round_base) * round_base)

                profits_used.add(profit)

                deposit_str = f"${deposit:,}"
                profit_str = f"${profit:,}"

                template = random.choice(SUCCESS_STORY_TEMPLATES[gender])
                story_text = f"{name} {template.replace('${deposit}', deposit_str).replace('${profit}', profit_str)}"

                conn.execute(success_stories.insert().values(
                    trader_name=name,
                    gender=gender,
                    story=story_text,
                    image=image_url  # save URL instead of local path
                ))

                stories[gender].append({
                    "name": name,
                    "story": story_text,
                    "image": image_url
                })

        return stories

TRADER_STORIES = initialize_stories()

# Success story templates with dynamic placeholders
SUCCESS_STORY_TEMPLATES = {
    "male": [
        "transformed a modest ${deposit} investment into an impressive ${profit} through a meticulously planned swing trade on AAPL.",
        "turned ${deposit} into a remarkable ${profit} by mastering the art of BTC HODL.",
        "flipped a ${deposit} stake into ${profit} with a bold NIKY pump riding move.",
        "achieved a stunning ${profit} profit from a strategic ETH DCA plan starting with ${deposit}.",
        "earned ${profit} through a clever SOL arbitrage play after investing ${deposit}."
    ],
    "female": [
        "grew a ${deposit} investment into ${profit} with a disciplined TSLA scalping strategy.",
        "boosted ${deposit} into ${profit} with an early sniping move on DOGE.",
        "turned ${deposit} into ${profit} via a SHIB community flip.",
        "made ${profit} from a NVDA position trade starting with ${deposit}.",
        "grew ${deposit} into ${profit} with a GOOGL day trading plan."
    ]
}

# Helper to fetch DB posts
def fetch_recent_profits():
    try:
        with engine.connect() as conn:
            stmt = select(posts.c.profit).where(posts.c.profit != None).order_by(posts.c.posted_at.desc()).limit(50)
            result = conn.execute(stmt).scalars().all()
            return set(result)
    except Exception as e:
        logger.error(f"Database error: {e}")
        return set()

# Helper: Generate profit scenario with realistic gains
def generate_profit_scenario(symbol):
    """
    Generate realistic profit scenario with capped bands:
    - Meme coins:
        • Common: $1k–$10k
        • Less common: $10k–$20k
        • Rare flex: up to $70k (very low chance)
    - Stocks/Crypto:
        • Common: $500–$5k
        • Less common: $5k–$8k
        • Rare whale: up to $55k (very low chance)
    """

    # --- Meme coins ---
    if symbol in MEME_COINS:
        r = random.random()
        if r < 0.75:    # 75% common
            profit = random.randint(1000, 10000)
        elif r < 0.95:  # 20% less common
            profit = random.randint(10000, 20000)
        else:           # 5% rare moonshot
            profit = random.randint(20000, 70000)

    # --- Stocks & Crypto ---
    else:
        r = random.random()
        if r < 0.75:    # 75% common
            profit = random.randint(500, 5000)
        elif r < 0.95:  # 20% less common
            profit = random.randint(5000, 8000)
        else:           # 5% rare whale
            profit = random.randint(8000, 55000)

    # Back-calc deposit & ROI so it looks consistent
    multiplier = random.uniform(2, 6)  # moderate leverage range
    deposit = max(100, int(profit / multiplier))
    roi = round((profit / deposit - 1) * 100, 1)

    # Trading style & reason
    if symbol in STOCK_SYMBOLS:
        trading_style = random.choice(["Scalping", "Day Trade", "Swing Trade", "Position"])
        reason = f"{symbol} {trading_style} setup worked perfectly!"
    elif symbol in CRYPTO_SYMBOLS:
        trading_style = random.choice(["HODL", "Swing Trade", "Leverage", "Arbitrage"])
        reason = f"{symbol} {trading_style} breakout gave solid returns!"
    else:
        trading_style = random.choice(["Pump Riding", "Community Flip", "Early Sniping"])
        reason = f"{symbol} {trading_style} run delivered massive gains!"

    return deposit, profit, roi, reason, trading_style
    
    # 🎲 Weighted multipliers: heavy tail for memes, tamer for stocks/crypto
    def weighted_multiplier(is_meme: bool) -> float:
        if is_meme:
            # Buckets (low/med/high/super) with probabilities
            buckets = [
                ( (2.0, 4.0),  0.45 ),   # most often 2–4×
                ( (4.0, 8.0),  0.30 ),   # sometimes 4–8×
                ( (8.0, 12.0), 0.18 ),   # less often 8–12×
                ( (12.0, 20.0),0.07 ),   # rare 12–20× bombs
            ]
        else:
            buckets = [
                ( (2.0, 3.0),  0.55 ),   # most often 2–3×
                ( (3.0, 4.0),  0.25 ),   # sometimes 3–4×
                ( (4.0, 5.0),  0.15 ),   # less often 4–5×
                ( (5.0, 6.0),  0.05 ),   # rare 5–6× spikes
            ]
        r = random.random()
        cum = 0.0
        for (low, high), p in buckets:
            cum += p
            if r <= cum:
                return random.uniform(low, high)
        low, high = buckets[-1][0]
        return random.uniform(low, high)

    is_meme = symbol in MEME_COINS
    deposit = random.choice(meme_deposits if is_meme else spot_deposits)

    # pick a multiplier with the weighted dist above
    mult = weighted_multiplier(is_meme)
    raw_profit = deposit * mult

    # make numbers look “human” (rounded but not too perfect)
    profit = int(raw_profit // 50 * 50)
    while profit in recent_profits:
        mult = weighted_multiplier(is_meme)
        profit = int((deposit * mult) // 50 * 50)

    multiplier = profit / deposit
    percentage_gain = round((multiplier - 1) * 100, 1)

    # price move shown in the blurb (loosely tied to ROI so it feels plausible)
    price_increase = int(percentage_gain * random.uniform(0.7, 1.1))

    if symbol in STOCK_SYMBOLS:
        trading_style = random.choice(["Scalping", "Day Trading", "Swing Trade", "Position Trade"])
        reasons = [
            f"{symbol} {trading_style} climbed {price_increase}% in a steady rally!",
            f"Solid {trading_style} on {symbol} yielded {price_increase}%!",
            f"{symbol} rose {price_increase}% on {trading_style} strategy!",
            f"Market favored {symbol} with {price_increase}% in {trading_style}!",
            f"{trading_style} on {symbol} delivered {price_increase}% returns!",
        ]
    elif symbol in CRYPTO_SYMBOLS:
        trading_style = random.choice(["HODL", "Swing Trade", "DCA", "Arbitrage", "Leverage Trading"])
        reasons = [
            f"{symbol} {trading_style} gained {price_increase}% on market trends!",
            f"{trading_style} on {symbol} secured {price_increase}%!",
            f"{symbol} increased {price_increase}% with {trading_style} approach!",
            f"Crypto {trading_style} lifted {symbol} by {price_increase}%!",
            f"Steady {price_increase}% gain on {symbol} via {trading_style}!",
        ]
    else:
        trading_style = random.choice(["Early Sniping", "Pump Riding", "Community Flip", "Airdrop Hunt"])
        reasons = [
            f"{symbol} gained {price_increase}% after a market boost!",
            f"Community drove {symbol} up {price_increase}%!",
            f"{symbol} surged {price_increase}% on trending news!",
            f"Strategic {trading_style} yielded {price_increase}% on {symbol}!",
            f"{symbol} rose {price_increase}% with smart timing!",
        ]

    return deposit, profit, percentage_gain, random.choice(reasons), trading_style

# ---------------------------
# Leaderboard Helpers
# ---------------------------
def fetch_cached_rankings():
    """
    Return current leaderboard from DB (Top 10).
    """
    with engine.begin() as conn:
        row = conn.execute(select(rankings_cache)).fetchone()
        if not row:
            return []
        return [line for line in row.content.split("\n") if line.strip()]


def save_rankings(parsed):
    """
    Save top 10 traders to DB with medals and return formatted lines.
    Always overwrite numbering so no duplicates like '4. 9.' appear.
    """
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for i, (name, total) in enumerate(parsed, start=1):
        badge = medals.get(i, f"{i}.")   # force clean numbering
        lines.append(f"{badge} {name} — ${total:,} profit")

    with engine.begin() as conn:
        conn.execute(delete(rankings_cache))
        conn.execute(insert(rankings_cache).values(
            content="\n".join(lines),
            timestamp=datetime.now(timezone.utc)
        ))
    return lines


def update_rankings_with_new_profit(trader_name, new_profit):
    """
    Update leaderboard cumulative totals.
    Ensures numbering and medals are fully reset each time.
    """
    parsed = fetch_cached_rankings()

    clean = []
    for line in parsed:
        try:
            # Strip all emojis, medals, and numbering completely
            raw = line.split("—")[0].strip()
            raw = raw.replace("🥇", "").replace("🥈", "").replace("🥉", "")
            raw = "".join([c for c in raw if not c.isdigit() and c not in "."])  # strip stray numbers and dots
            name = raw.strip()

            profit = int(line.split("$")[-1].split()[0].replace(",", ""))
            clean.append((name, profit))
        except:
            continue

    # If empty, seed new board
    if not clean:
        selected = random.sample(RANKING_TRADERS, 10)
        clean = [(name, random.randint(2000, 8000)) for _, name in selected]

    # Update or add trader
    found = False
    for i, (name, total) in enumerate(clean):
        if name == trader_name:
            clean[i] = (trader_name, total + new_profit)
            found = True
            break
    if not found:
        clean.append((trader_name, new_profit))

    # Sort & keep top 10
    clean.sort(key=lambda x: x[1], reverse=True)
    clean = clean[:10]

    # Save back with **fresh numbering**
    lines = save_rankings(clean)

    # Get position
    pos = None
    for i, (name, _) in enumerate(clean, start=1):
        if name == trader_name:
            pos = i
            break

    return lines, pos

def craft_profit_message(symbol, deposit, profit, percentage_gain, reason, trading_style):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    multiplier = round(profit / deposit, 1)

    # Use cached rankings instead of fetch_user_stats()
    social_lines = fetch_cached_rankings()
    social_text = "\n".join(social_lines)

    mention = random.choice(RANKING_TRADERS)[1]
    tag = "#MemeCoinGains #CryptoTrends" if symbol in MEME_COINS else "#StockMarket #CryptoWins"
    asset_desc = "Meme Coin" if symbol in MEME_COINS else symbol

    msg = (
        f"📈 <b>{symbol} Profit Update</b> 📈\n"
        f"<b>{trading_style}</b> on {asset_desc}\n"
        f"💰 Invested: ${deposit:,.2f}\n"
        f"🎯 {multiplier}x Return → Realized: ${profit:,.2f}\n"
        f"🔥 {reason}\n"
        f"📊 Achieved {percentage_gain}% ROI!\n"
        f"Time: {ts}\n\n"
        f"🏆 Top Trader Rankings:\n{social_text}\n"
        f"👉 Shoutout to {mention} for inspiring us!\n\n"
        f"Join us at Options Trading University for more insights! {tag}"
    )

    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return msg, reply_markup

def craft_success_story(current_index, gender):
    combined = [("male", s) for s in TRADER_STORIES["male"]] + [("female", s) for s in TRADER_STORIES["female"]]
    total = len(combined)
    current_index = current_index % total
    gender, story_data = combined[current_index]

    story = story_data["story"]
    image_url = story_data["image"]  # already a GitHub URL

    keyboard = [
        [InlineKeyboardButton("⬅️ Prev", callback_data=f"success_prev_{gender}_{current_index}")],
        [InlineKeyboardButton("➡️ Next", callback_data=f"success_next_{gender}_{current_index}")],
        [InlineKeyboardButton("Back to Menu", callback_data="back")]
    ]

    return story, InlineKeyboardMarkup(keyboard), image_url
def craft_trade_status():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    social_lines = fetch_cached_rankings()
    return (
        f"🏆 <b>Top Trader Rankings</b> 🏆\n"
        f"As of {ts}:\n"
        f"{'\n'.join(social_lines)}\n\n"
        f"Join the community at Options Trading University for more trading insights! #TradingCommunity"
    ), InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]])
# Log post content to DB and update user profits
def log_post(symbol, content, deposit, profit, user_id=None):
    try:
        with engine.begin() as conn:
            if user_id:
                stmt = users.update().where(users.c.user_id == str(user_id)).values(
                    total_profit=users.c.total_profit + profit
                )
                conn.execute(stmt)

            stmt = posts.insert().values(
                symbol=symbol,
                content=content,
                deposit=deposit,
                profit=profit,
                posted_at=datetime.now(timezone.utc)
            )
            conn.execute(stmt)
    except Exception as e:
        logger.error(f"Database error: {e}")

def short_highlight(symbol: str, profit: float, percentage_gain: float) -> str:
    """
    A compact caption for photo when your full message is too long for Telegram caption.
    """
    return f"+${profit:,.0f} on {symbol} • ROI {percentage_gain:.1f}% 🔥"

import io, random
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

# ============ FONT LOADER ============
def load_font(size, bold=False):
    """Try to load DejaVu font, fallback to default if missing (Railway safe)."""
    try:
        if bold:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        else:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except:
        return ImageFont.load_default()

# ============ IMAGE GENERATOR ============
def generate_profit_card(symbol, profit, roi, deposit, trader_name="TraderX"):
    """
    Generate a compact, realistic profit report card image.
    Returns an in-memory PNG buffer.
    """
    W, H = 600, 800  # compact canvas

    # Fonts (safe loader)
    big_font = load_font(60, bold=True)
    med_font = load_font(32, bold=True)
    small_font = load_font(22)

    # Background gradient
    bg = Image.new("RGB", (W, H), (20, 60, 180))
    gradient = Image.new("RGB", (1, H))
    for y in range(H):
        gradient.putpixel((0, y), (20, 40 + y // 8, 120 + y // 10))
    gradient = gradient.resize((W, H))
    bg = Image.blend(bg, gradient, 0.7)

    draw = ImageDraw.Draw(bg)

    # White central panel
    panel_h = 300
    panel = Image.new("RGB", (W-80, panel_h), "white")
    bg.paste(panel, (40, 220))

    # Text inside
    draw.text((W//2, 250), f"{symbol} Profit Report", fill=(20,40,80), font=med_font, anchor="mm")
    draw.text((W//2, 350), f"+${profit:,.0f}", fill="#22c55e", font=big_font, anchor="mm")
    draw.text((W//2, 420), f"ROI: {roi:.1f}%", fill="#f59e0b", font=med_font, anchor="mm")
    draw.text((W//2, 480), f"Deposit: ${deposit:,}", fill=(30,30,30), font=med_font, anchor="mm")

    # Footer overlay
    footer_h = 70
    overlay = Image.new("RGBA", (W, footer_h), (0,0,0,160))
    bg.paste(overlay, (0, H-footer_h), overlay)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    broker = random.choice(["Webull", "Robinhood", "Fidelity", "Thinkorswim", "E*TRADE"])
    draw.text((W//2, H-50), f"{trader_name} • {ts}", fill="white", font=small_font, anchor="mm")
    draw.text((W//2, H-25), broker, fill="#22c55e", font=small_font, anchor="mm")

    buf = io.BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ======================
# Short caption fallback
# ======================
def short_highlight(symbol: str, profit: float, roi: float) -> str:
    return f"+${profit:,.0f} on {symbol} • ROI {roi:.1f}% 🔥"

# ======================
# ======================

ADMIN_ID = os.getenv("ADMIN_ID")

async def profit_posting_loop(app):
    global last_category
    logger.info("Profit posting task started.")
    while True:
        try:
            # Wait time between posts: 80% short (2–10 min), 20% long (20–30 min)
            wait_minutes = random.randint(2, 10) if random.random() < 0.8 else random.randint(20, 30)
            await asyncio.sleep(wait_minutes * 60)

            # 🎯 Weighted category selection (50% stocks, 40% meme coins, 10% crypto)
            r = random.random()
            if r < 0.5:
                category = "stock"
            elif r < 0.9:
                category = "meme"
            else:
                category = "crypto"

            # Prevent repeating same category twice
            if category == last_category:
                if category == "stock":
                    category = "meme" if random.random() < 0.7 else "crypto"
                elif category == "meme":
                    category = "stock" if random.random() < 0.7 else "crypto"
                else:
                    category = "stock"

            last_category = category

            # Pick symbol based on chosen category
            if category == "stock":
                symbol = random.choice(STOCK_SYMBOLS)
            elif category == "meme":
                symbol = random.choice(MEME_COINS)
            else:
                symbol = random.choice(CRYPTO_SYMBOLS)

            # Generate scenario
            deposit, profit, roi, reason, trading_style = generate_profit_scenario(symbol)

            # Update rankings
            trader_id, trader_name = random.choice(RANKING_TRADERS)
            rankings, pos = update_rankings_with_new_profit(trader_name, profit)

            # Build caption
            msg = (
                f"📈 <b>{symbol} Profit Update</b>\n"
                f"👤 Trader: {trader_name}\n"
                f"💰 Invested: ${deposit:,}\n"
                f"🎯 Profit: ${profit:,} (+{roi}%)\n"
                f"📊 Strategy: {trading_style}\n"
                f"🔥 {reason}\n\n"
                f"🏆 Top 10 Traders:\n" + "\n".join(rankings)
            )

            # Generate image
            img_buf = generate_profit_card(symbol, profit, roi, deposit, trader_name)

            # Send to Telegram group
            await app.bot.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                photo=img_buf,
                caption=msg,
                parse_mode=constants.ParseMode.HTML
            )

            # DM confirmation
            if ADMIN_ID:
                confirm = f"✅ Auto-posted {symbol} profit: ${profit:,} ({category}) at {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
                await app.bot.send_message(chat_id=ADMIN_ID, text=confirm)

            # 🎉 Optional hype message
            if pos:
                hype = None
                if pos == 1:
                    hype = f"🚀 {trader_name} just TOOK the #1 spot with ${profit:,}! Legendary move!"
                elif pos <= 3:
                    hype = f"🔥 {trader_name} broke into the Top 3 with ${profit:,}!"
                elif pos <= 10 and random.random() < 0.25:
                    hype = f"💪 {trader_name} entered the Top 10 with ${profit:,}!"
                if hype:
                    await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=hype)

        except Exception as e:
            logger.error(f"Error in posting loop: {e}")
            if ADMIN_ID:
                await app.bot.send_message(chat_id=ADMIN_ID, text=f"❌ Error in posting loop: {e}")
            await asyncio.sleep(5)

async def manual_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_category
    user_id = str(update.effective_user.id)

    # Restrict to admin
    if user_id != str(ADMIN_ID):
        await update.message.reply_text("🚫 You are not authorized to trigger manual posts.")
        return

    # 🎯 Weighted category selection (50% stocks, 40% meme coins, 10% crypto)
    r = random.random()
    if r < 0.5:
        category = "stock"
    elif r < 0.9:
        category = "meme"
    else:
        category = "crypto"

    # Prevent repeating same type twice
    if category == last_category:
        if category == "stock":
            category = "meme" if random.random() < 0.7 else "crypto"
        elif category == "meme":
            category = "stock" if random.random() < 0.7 else "crypto"
        else:
            category = "stock"

    last_category = category

    # Pick symbol
    if category == "stock":
        symbol = random.choice(STOCK_SYMBOLS)
    elif category == "meme":
        symbol = random.choice(MEME_COINS)
    else:
        symbol = random.choice(CRYPTO_SYMBOLS)

    # Generate profit scenario
    deposit, profit, roi, reason, trading_style = generate_profit_scenario(symbol)
    trader_id, trader_name = random.choice(RANKING_TRADERS)
    rankings, pos = update_rankings_with_new_profit(trader_name, profit)

    msg = (
        f"📈 <b>{symbol} Profit Update</b>\n"
        f"👤 Trader: {trader_name}\n"
        f"💰 Invested: ${deposit:,}\n"
        f"🎯 Profit: ${profit:,} (+{roi}%)\n"
        f"📊 Strategy: {trading_style}\n"
        f"🔥 {reason}\n\n"
        f"🏆 Top 10 Traders:\n" + "\n".join(rankings)
    )

    img_buf = generate_profit_card(symbol, profit, roi, deposit, trader_name)

    await context.bot.send_photo(
        chat_id=TELEGRAM_CHAT_ID,
        photo=img_buf,
        caption=msg,
        parse_mode=constants.ParseMode.HTML
    )

    await update.message.reply_text(f"✅ Manual profit update posted ({category}).")

    # Hype message
    if pos:
        hype = None
        if pos == 1:
            hype = f"🚀 {trader_name} just TOOK the #1 spot with ${profit:,}! Legendary move!"
        elif pos <= 3:
            hype = f"🔥 {trader_name} broke into the Top 3 with ${profit:,}!"
        elif pos <= 10 and random.random() < 0.25:
            hype = f"💪 {trader_name} entered the Top 10 with ${profit:,}!"
        if hype:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=hype)
# /start handler with Top 3 Rankings
# ================================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    name = user.first_name or user.username or "Trader"

    # ✅ Alert admin that user interacted
    await alert_admin_user_action(update, "/start command")

    # ✅ Get leaderboard (cached or rebuilt if needed)
    social_lines = fetch_cached_rankings()  # returns sorted list
    top3 = "\n".join(social_lines[:3]) if social_lines else "No rankings yet."

    # Pick a random success story index
    total_stories = len(TRADER_STORIES["male"]) + len(TRADER_STORIES["female"])
    random_index = random.randint(0, total_stories - 1)

    # Inline buttons
    keyboard = [
        [InlineKeyboardButton("📊 Full Rankings", callback_data="rankings"),
         InlineKeyboardButton("📖 Success Stories", callback_data=f"success_any_{random_index}")],
        [InlineKeyboardButton("📢 Join Profit Group", url="https://t.me/+v2cZ4q1DXNdkMjI8")],
        [InlineKeyboardButton("🌐 Visit Website", url=WEBSITE_URL),
         InlineKeyboardButton("📜 Terms", callback_data="terms")],
        [InlineKeyboardButton("🔒 Privacy", callback_data="privacy")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Welcome message
    welcome_text = (
        f"👋 Welcome, <b>{name}</b>!\n\n"
        f"At <b>Options Trading University</b>, we provide expert-led training, live profit flexes, "
        f"and a thriving trader community.\n\n"
        f"🔥 Here are today’s <b>Top 3 Traders</b>:\n"
        f"{top3}\n\n"
        f"Why join us?\n"
        f"- 💸 Real trades with 2x–8x on Stocks/Crypto\n"
        f"- 🚀 Meme Coin Moonshots up to 100x\n"
        f"- 📖 Inspiring success stories\n\n"
        f"Start your journey to financial growth today!"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=welcome_text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )

    # ✅ Store user in DB
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO users (user_id, username, display_name, wins, total_trades, total_profit)
                VALUES (:id, :u, :d, 0, 0, 0)
                ON CONFLICT(user_id) DO NOTHING
            """), {
                "id": str(user.id),
                "u": user.username or "unknown",
                "d": name
            })
    except Exception as e:
        logger.error(f"Error adding user {user.id}: {e}")


# ================================
# Admin Alert Helper
# ================================
async def alert_admin_user_action(update, action):
    """Send an alert DM to admin whenever someone interacts with the bot"""
    if ADMIN_ID:
        user = update.effective_user
        username = f"@{user.username}" if user.username else user.full_name
        alert_text = f"👤 {username} ({user.id}) used: {action}"
        await update.get_bot().send_message(chat_id=ADMIN_ID, text=alert_text)


# Callback handler for inline buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await alert_admin_user_action(update, f"Pressed button: {query.data}")
    # ... (rest of your button code)
# query = update.callback_query
    await query.answer()
    data = query.data

    if data == "rankings":
        status_msg, status_reply_markup = craft_trade_status()
        await query.edit_message_text(
            text=status_msg,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=status_reply_markup
        )

    elif data.startswith("success_"):
        parts = data.split("_")

        # success_any_3
        if parts[1] == "any":
            index = int(parts[2])
            gender = "any"

        # success_prev_male_3 or success_next_female_2
        elif parts[1] in ["prev", "next"]:
            action, gender, index = parts[1], parts[2], int(parts[3])
            index = index - 1 if action == "prev" else index + 1
        else:
            await query.edit_message_text("⚠️ Invalid success story request.")
            return

        # Get story
        story, reply_markup, image_url = craft_success_story(index, gender)

        if image_url and image_url.startswith("http"):
            from telegram import InputMediaPhoto
            try:
                await query.edit_message_media(
                    media=InputMediaPhoto(
                        media=image_url,
                        caption=f"📖 <b>Success Story</b>:\n{story}\n\nJoin Options Trading University to start your own journey!",
                        parse_mode=constants.ParseMode.HTML
                    ),
                    reply_markup=reply_markup
                )
            except Exception:
                # If edit fails (e.g. original was text), send new message
                await query.message.reply_photo(
                    photo=image_url,
                    caption=f"📖 <b>Success Story</b>:\n{story}\n\nJoin Options Trading University to start your own journey!",
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=reply_markup
                )
        else:
            await query.edit_message_text(
                text=f"📖 <b>Success Story</b>:\n{story}\n\nJoin Options Trading University to start your own journey!",
                parse_mode=constants.ParseMode.HTML,
                reply_markup=reply_markup
            )

    elif data == "terms":
        terms_text = (
            f"📜 <b>Terms of Service</b> 📜\n\n"
            f"1. Acceptance of Terms: By using this bot, you agree to abide by these Terms of Service.\n"
            f"2. User Conduct: Users must comply with all applicable laws and not use the bot for illegal activities.\n"
            f"3. Disclaimer: All trading insights are for informational purposes only and not financial advice.\n"
            f"4. Limitation of Liability: Options Trading University is not liable for any losses incurred.\n"
            f"5. Changes to Terms: We may update these terms at any time. Continued use constitutes acceptance.\n\n"
            f"For full terms, visit our website."
        )
        keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="back")]]
        await query.edit_message_text(
            text=terms_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "privacy":
        privacy_text = (
            f"🔒 <b>Privacy Policy</b> 🔒\n\n"
            f"1. Information Collected: We collect minimal data such as user IDs and usernames for bot functionality.\n"
            f"2. Use of Data: Data is used to personalize experiences and improve services.\n"
            f"3. Data Sharing: We do not sell your data. It may be shared with partners for service improvement.\n"
            f"4. Security: We use industry-standard measures to protect your data.\n"
            f"5. Changes to Policy: We may update this policy. Continued use constitutes acceptance.\n\n"
            f"For full privacy policy, visit our website."
        )
        keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="back")]]
        await query.edit_message_text(
            text=privacy_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "back":
        # 👇 Build the /start main menu again
        total_stories = len(TRADER_STORIES["male"]) + len(TRADER_STORIES["female"])
        random_index = random.randint(0, total_stories - 1)

        keyboard = [
            [InlineKeyboardButton("View Rankings", callback_data="rankings"),
             InlineKeyboardButton("Success Stories", callback_data=f"success_any_{random_index}")],
            [InlineKeyboardButton("Visit Website", url=WEBSITE_URL),
             InlineKeyboardButton("Terms of Service", callback_data="terms")],
            [InlineKeyboardButton("Privacy Policy", callback_data="privacy")]
        ]

        welcome_text = (
            f"📌 OPTIONS TRADING\n\n"
            f"At Options Trading University, we provide expert-led training, real-time market analysis, "
            f"and a thriving community of successful traders.\n\n"
            f"Why join us?\n"
            f"- Access to high-probability trades (up to 900% gains on meme coins).\n"
            f"- Guidance from top traders with a track record of success.\n"
            f"- Exclusive insights on stocks, crypto, and meme coins.\n\n"
            f"Start your journey to financial growth today!"
        )

        # Always send fresh new message so it works after photos/captions
        await query.message.reply_text(
            text=welcome_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
   
    #/status handler
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📈 <b>Market Overview</b> 📊\n"
        f"Stocks: {', '.join(STOCK_SYMBOLS)}\n"
        f"Crypto: {', '.join(CRYPTO_SYMBOLS)}\n"
        f"Meme Coins: {', '.join(MEME_COINS)}\n"
        f"Profit updates drop every 20-40 minutes with gains up to 900%!\n\n"
        f"Join the action at Options Trading University! #TradingCommunity"
    )
    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )

# /help handler
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"ℹ️ <b>Help & Commands</b> ℹ️\n"
        f"/start - Welcome message and community link\n"
        f"/status - View current market focus\n"
        f"/trade_status - Check top trader rankings\n"
        f"/help - Display this help menu\n\n"
        f"Profit updates auto-post every 20-40 minutes. Join us at Options Trading University! #TradingSuccess"
    )
    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )

# ---------------------------
# /trade_status handler
# ---------------------------
async def trade_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rankings = fetch_cached_rankings()

    if not rankings:
        msg = "🏆 Leaderboard is still warming up... no entries yet!"
    else:
        msg = (
            f"🏆 <b>Top 10 Trader Rankings</b>\n"
            f"As of {ts}:\n\n" +
            "\n".join(rankings) +
            "\n\nKeep grinding — next profit update could shake things up!"
        )

    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================================
# Startup + Main
# ================================

async def on_startup(app):
    """Notify admin and start the profit posting loop when bot launches."""
    logger.info("Bot started. Launching posting loop…")
    app.create_task(profit_posting_loop(app))
    if ADMIN_ID:
        await app.bot.send_message(
            chat_id=ADMIN_ID,
            text="✅ Bot is alive and posting loop started!"
        )

def main():
    if TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None:
        raise SystemExit("❌ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in .env")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("trade_status", trade_status_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("resetdb", resetdb_handler))
    app.add_handler(CommandHandler("postprofit", manual_post_handler))

    # Hook startup event
    app.post_init = on_startup

    logger.info("🚀 Bot application built and ready.")
    app.run_polling()

# Run main
if __name__ == "__main__":
    main()
