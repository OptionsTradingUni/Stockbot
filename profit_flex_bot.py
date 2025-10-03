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
    Drops ALL tables in the connected Postgres DB,
    then recreates them using metadata.
    """
    with engine.begin() as conn:
        # Drop all tables (cascade = remove dependencies)
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))

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
    Generate realistic profit scenarios:
    - Common profits: 4k–18k
    - Small occasional: 1k–3k
    - Rare big: 20k–40k
    - Very rare moonshot: 50k+
    """
    recent_profits = fetch_recent_profits()

    # --- MEME COINS ---
    if symbol in MEME_COINS:
        deposit = random.randint(500, 5000)

        r = random.random()
        if r < 0.10:  # 10% → small profits (1–3k)
            mult = random.uniform(2, 6)
        elif r < 0.80:  # 70% → normal (4–18k range)
            mult = random.uniform(5, 15)
        elif r < 0.95:  # 15% → bigger (20–40k)
            mult = random.uniform(15, 30)
        else:  # 5% → moonshot 50k+
            mult = random.uniform(40, 80)

        profit = int((deposit * mult) // 50 * 50)

    # --- STOCKS / CRYPTO ---
    else:
        deposit = random.randint(500, 3000)
        r = random.random()
        if r < 0.15:  # 15% → 1–3k
            mult = random.uniform(2, 4)
        elif r < 0.85:  # 70% → 4–18k
            mult = random.uniform(2.5, 6)
        elif r < 0.95:  # 10% → 20–40k
            deposit = random.randint(5000, 15000)
            mult = random.uniform(2, 4)
        else:  # 5% → rare 50k+
            deposit = random.randint(10000, 20000)
            mult = random.uniform(3, 5)

        profit = int((deposit * mult) // 50 * 50)

    # --- Avoid duplicates ---
    tries = 0
    while profit in recent_profits and tries < 10:
        profit = int((deposit * random.uniform(2, 8)) // 50 * 50)
        tries += 1

    percentage_gain = round((profit / deposit - 1) * 100, 1)

    # --- Narratives ---
    if symbol in STOCK_SYMBOLS:
        trading_style = random.choice(["Scalping", "Day Trading", "Swing Trade", "Position Trade"])
        reasons = [
            f"{symbol} {trading_style} climbed on momentum!",
            f"Solid {trading_style} execution on {symbol}.",
            f"{symbol} strength confirmed by clean {trading_style}.",
            f"Market favored {symbol} with strong {trading_style} follow-through.",
        ]
    elif symbol in CRYPTO_SYMBOLS:
        trading_style = random.choice(["HODL", "Swing Trade", "DCA", "Arbitrage", "Leverage Trading"])
        reasons = [
            f"{symbol} {trading_style} rode a liquidity wave.",
            f"{trading_style} on {symbol} aligned with breakout.",
            f"{symbol} breakout + {trading_style} worked well.",
            f"Disciplined {trading_style} structure lifted {symbol}.",
        ]
    else:
        trading_style = random.choice(["Early Sniping", "Pump Riding", "Community Flip", "Airdrop Hunt"])
        reasons = [
            f"{symbol} squeeze extended with {trading_style}.",
            f"Community traction sent {symbol} higher.",
            f"{symbol} trend pop after fresh flows.",
            f"Smart {trading_style} timing on {symbol}.",
        ]

    reason = random.choice(reasons) + f" (+{percentage_gain}%)"
    return deposit, profit, percentage_gain, reason, trading_style

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
    Save top 10 traders to DB with medals and return lines.
    """
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for i, (name, total) in enumerate(parsed, start=1):
        badge = medals.get(i, f"{i}.")
        lines.append(f"{badge} <b>{name}</b> — ${total:,} profit")

    with engine.begin() as conn:
        conn.execute(delete(rankings_cache))
        conn.execute(insert(rankings_cache).values(
            content="\n".join(lines),
            timestamp=datetime.now(timezone.utc)
        ))
    return lines


def update_rankings_with_new_profit(trader_name, new_profit):
    """
    Insert into leaderboard if profit > lowest current (Top 10).
    Keeps only Top 10.
    Returns: (lines, newcomer_position or None)
    """
    parsed = fetch_cached_rankings()

    # If no leaderboard yet, seed it with random traders
    if not parsed:
        selected = random.sample(RANKING_TRADERS, 10)
        parsed = [(name, random.randint(4000, 18000)) for _, name in selected]

    # Convert parsed back to list of tuples
    clean = []
    for line in parsed:
        try:
            name = line.split("—")[0].split("</b>")[0].split("<b>")[-1].strip()
            profit = int(line.split("$")[-1].split()[0].replace(",", ""))
            clean.append((name, profit))
        except:
            continue

    parsed = clean

    # If profit not big enough, ignore
    if len(parsed) >= 10:
        threshold = parsed[-1][1]
        if new_profit <= threshold:
            return save_rankings(parsed), None

    # Insert and sort
    parsed.append((trader_name, new_profit))
    parsed.sort(key=lambda x: x[1], reverse=True)
    parsed = parsed[:10]

    # Save back
    lines = save_rankings(parsed)

    # Newcomer position
    pos = [p[0] for p in parsed].index(trader_name) + 1
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


import random, io
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def _fake_price_path(n=60, base=100.0, vol=1.2):
    """Generate fake sparkline price path"""
    x = np.arange(n)
    y = np.cumsum(np.random.randn(n) * vol) + base
    return x, y

def generate_pl_image(symbol, deposit, profit, roi_percent, trader_name="Anonymous"):
    """
    Create a stylish P/L image.
    Main format = 'card' (clean stats), with rare 'big' + 'split'.
    Returns a file path to a PNG image.
    """
    style = random.choices(
        ["card", "big", "split"],
        weights=[0.7, 0.15, 0.15],  # card is most common
        k=1
    )[0]

    dark_bg = "#0d1117"
    dark_panel = "#161b22"
    accent_options = ["#22c55e", "#3b82f6", "#f59e0b", "#a855f7", "#ef4444"]
    accent = random.choice(accent_options)

    if style in ("card", "big"):
        fig, ax = plt.subplots(figsize=(6, 3.6), dpi=140)
        fig.patch.set_facecolor(dark_bg)
        ax.set_facecolor(dark_panel)
        ax.axis("off")

    if style == "card":
        ax.text(0.5, 0.92, f"{symbol} Profit Update", ha="center", va="center",
                fontsize=17, color="white", fontweight="bold")

        # Sparkline
        x, y = _fake_price_path(n=50, base=100.0, vol=random.uniform(0.8, 1.8))
        ax.plot(x, y, lw=2.2, color=accent, alpha=0.85)
        ax.fill_between(x, y, y2=y.min(), color=accent, alpha=0.12)

        # Stats block
        ax.text(0.08, 0.65, f"Deposit", fontsize=10, color="#9ca3af")
        ax.text(0.08, 0.56, f"${deposit:,.0f}", fontsize=16, color="white", fontweight="bold")

        ax.text(0.40, 0.65, f"Profit", fontsize=10, color="#9ca3af")
        ax.text(0.40, 0.56, f"${profit:,.0f}", fontsize=16, color="#22c55e", fontweight="bold")

        ax.text(0.72, 0.65, f"ROI", fontsize=10, color="#9ca3af")
        ax.text(0.72, 0.56, f"{roi_percent:.1f}%", fontsize=16, color="#f59e0b", fontweight="bold")

        ax.text(0.08, 0.20, f"Trader: {trader_name}", fontsize=11, color="#e5e7eb")
        ax.text(0.72, 0.20, datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
                fontsize=9, color="#9ca3af", ha="right")

    elif style == "big":
        ax.text(0.5, 0.82, f"{symbol}", ha="center", va="center",
                fontsize=20, color="white", fontweight="bold")
        ax.text(0.5, 0.56, f"+${profit:,.0f}", ha="center", va="center",
                fontsize=36, color=accent, fontweight="bold")
        ax.text(0.5, 0.38, f"ROI {roi_percent:.1f}% • Deposit ${deposit:,.0f}",
                ha="center", va="center", fontsize=12, color="#e5e7eb")
        ax.text(0.5, 0.18, f"Trader: {trader_name}",
                ha="center", va="center", fontsize=11, color="#9ca3af")

        circle = plt.Circle((0.5, 0.56), 0.32, transform=ax.transAxes, color=accent, alpha=0.08)
        ax.add_artist(circle)

    elif style == "split":
        W, H = 900, 520
        base = Image.new("RGB", (W, H), dark_bg)
        panel = Image.new("RGB", (W - 80, H - 80), dark_panel)
        panel = panel.filter(ImageFilter.GaussianBlur(0.5))
        base.paste(panel, (40, 40))

        draw = ImageDraw.Draw(base)
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        big_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 62)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)

        draw.text((60, 58), f"{symbol} Profit Update", font=title_font, fill="white")
        draw.text((60, 140), f"+${profit:,.0f}", font=big_font, fill=accent)
        draw.text((60, 250), f"Deposit: ${deposit:,.0f}", font=body_font, fill="#e5e7eb")
        draw.text((60, 290), f"ROI: {roi_percent:.1f}%", font=body_font, fill="#f59e0b")
        draw.text((60, 340), f"Trader: {trader_name}", font=body_font, fill="#9ca3af")
        draw.text((60, 400), datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                  font=small_font, fill="#6b7280")

        x, y = _fake_price_path(n=80, base=100, vol=random.uniform(0.8, 2.0))
        px = np.interp(x, (x.min(), x.max()), (W*0.60, W*0.92))
        py = np.interp(y, (y.min(), y.max()), (H*0.75, H*0.45))
        for i in range(len(px)-1):
            draw.line((px[i], py[i], px[i+1], py[i+1]), fill=accent, width=3)

        img_path = "pl_report.png"
        base.save(img_path, format="PNG")
        return img_path

    img_path = "pl_report.png"
    plt.savefig(img_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return img_path
# Profit Posting Loop with Images
# ================================
async def profit_posting_loop(app):
    logger.info("Profit posting task started.")
    while True:
        try:
            # ⏳ Random wait (weighted: short intervals more common)
            wait_minutes = random.choices(
                [2, 5, 6, 8, 10, 20, 25, 30, 35],
                weights=[20, 18, 18, 15, 15, 5, 4, 3, 2],  # bias toward shorter times
                k=1
            )[0]

            wait_seconds = wait_minutes * 60
            logger.info(f"Next profit post in {wait_minutes}m at {datetime.now(timezone.utc)}")
            await asyncio.sleep(wait_seconds)

            # 🔀 Pick a symbol
            if random.random() < 0.7:
                symbol = random.choice(MEME_COINS)
            else:
                symbol = random.choice([s for s in ALL_SYMBOLS if s not in MEME_COINS])

            # --- Profit Ranges ---
            if symbol in MEME_COINS:
                deposit = random.randint(500, 5000)
                mult = random.uniform(3, 15)
                if random.random() < 0.05:  # rare moonshot
                    mult = random.uniform(20, 60)
            else:
                r = random.random()
                if r < 0.6:  # common range
                    deposit = random.randint(400, 2500)
                    mult = random.uniform(2, 6)
                elif r < 0.9:  # less common, bigger
                    deposit = random.randint(3000, 7000)
                    mult = random.uniform(2, 5)
                else:  # rare whale
                    deposit = random.randint(20000, 40000)
                    mult = random.uniform(2, 4)

            profit = int((deposit * mult) // 50 * 50)
            percentage_gain = round((profit / deposit - 1) * 100, 1)

            trading_style = random.choice(["Scalping", "Day Trading", "Swing Trade", "Position Trade"])
            reason = f"{symbol} {trading_style} worked out perfectly! (+{percentage_gain}%)"

            # 👤 Pick a trader name
            trader_id, trader_name = random.choice(RANKING_TRADERS)

            # 🏆 Try update leaderboard
            rankings, pos = update_rankings_with_new_profit(trader_name, profit)

            # 📢 Main profit message (text)
            msg = (
                f"📈 <b>{symbol} Profit Update</b>\n"
                f"👤 Trader: {trader_name}\n"
                f"💰 Invested: ${deposit:,}\n"
                f"🎯 Profit: ${profit:,} (+{percentage_gain}%)\n"
                f"📊 Strategy: {trading_style}\n"
                f"🔥 {reason}\n\n"
                f"🏆 Top 10 Traders:\n" + "\n".join(rankings)
            )

            # ✅ Post to Telegram (image + caption)
            try:
                img_path = generate_pl_image(
                    symbol=symbol,
                    deposit=deposit,
                    profit=profit,
                    roi_percent=percentage_gain,
                    trader_name=trader_name
                )

                caption = msg
                if len(msg) > 900:
                    caption = short_highlight(symbol, profit, percentage_gain)

                with open(img_path, "rb") as f:
                    await app.bot.send_photo(
                        chat_id=TELEGRAM_CHAT_ID,
                        photo=f,
                        caption=caption,
                        parse_mode=constants.ParseMode.HTML
                    )

                if caption is not msg:
                    await app.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=msg,
                        parse_mode=constants.ParseMode.HTML
                    )

                logger.info(f"[PROFIT POSTED] {symbol} {trading_style} Deposit ${deposit:.2f} → Profit ${profit:.2f}")
                log_post(symbol, msg, deposit, profit)

            except Exception as e:
                logger.error(f"Failed to send profit with image: {e}")

            # 🚀 Hype message if leaderboard changes
            if pos:
                if pos == 1:
                    hype = f"🚀 {trader_name} just TOOK the #1 spot with ${profit:,}! Legendary move!"
                elif pos <= 3:
                    hype = f"🔥 {trader_name} broke into the Top 3 with ${profit:,}!"
                else:
                    hype = f"💪 {trader_name} entered the Top 10 with ${profit:,}!"
                await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=hype)

        except asyncio.CancelledError:
            logger.info("Profit posting loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in posting loop: {e}")
            await asyncio.sleep(5)
# -----------------------
# /start handler with Top 3 Rankings
# -----------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    name = user.first_name or user.username or "Trader"

    # ✅ Get leaderboard (cached or rebuilt if needed)
    social_lines = fetch_cached_rankings()  # already returns sorted list
    top3 = "\n".join(social_lines[:3]) if social_lines else "No rankings yet."

    # Pick a random success story index
    total_stories = len(TRADER_STORIES["male"]) + len(TRADER_STORIES["female"])
    random_index = random.randint(0, total_stories - 1)

    keyboard = [
        [InlineKeyboardButton("📊 Full Rankings", callback_data="rankings"),
         InlineKeyboardButton("📖 Success Stories", callback_data=f"success_any_{random_index}")],
        [InlineKeyboardButton("📢 Join Profit Group", url="https://t.me/+v2cZ4q1DXNdkMjI8")],
        [InlineKeyboardButton("🌐 Visit Website", url=WEBSITE_URL),
         InlineKeyboardButton("📜 Terms", callback_data="terms")],
        [InlineKeyboardButton("🔒 Privacy", callback_data="privacy")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

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
        
# Callback handler for inline buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
        # db 
async def resetdb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    # 🔐 Replace with your own Telegram ID so randoms can’t nuke your DB
    if user_id != "8083574070":
        await update.message.reply_text("🚫 You are not authorized to reset the database.")
        return

    reset_database()
    await update.message.reply_text("✅ Database has been reset and recreated.")
# /status handler
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

def main():
    if TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None:
        raise SystemExit("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in .env")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("trade_status", trade_status_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("resetdb", resetdb_handler))
    
    async def on_startup(app):
        app.create_task(profit_posting_loop(app))
        logger.info("Profit posting task scheduled on startup.")

    app.post_init = on_startup

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
