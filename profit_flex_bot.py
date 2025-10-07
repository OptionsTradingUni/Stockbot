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
from models import (engine, metadata, posts, users, success_stories, 
                    rankings_cache, trade_logs)
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
import io
import matplotlib
matplotlib.use("Agg")  # headless backend for servers
import matplotlib.pyplot as plt
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from traders import RANKING_TRADERS
from verification_texts import generate_unique_txid, get_random_verification
from telegram.error import TelegramError
from telegram.ext import MessageHandler, filters
from telegram.constants import ChatMemberStatus
# --- NEW: Import market data libraries ---
import yfinance as yf
from pycoingecko import CoinGeckoAPI


# Compatibility alias
def generate_txid():
    return generate_unique_txid(engine)
# --- NEW: Market Data Fetcher ---
cg = CoinGeckoAPI()
# Map common symbols to CoinGecko API IDs
# In profit_flex_bot.py


CRYPTO_ID_MAP = {
    # Main Crypto
    "BTC": "bitcoin", 
    "ETH": "ethereum", 
    "SOL": "solana",
    "DOT": "polkadot",
    "XRP": "ripple",
    "ADA": "cardano",
    "SUI": "sui",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "XLM": "stellar", # <-- ADDED
    
    # Meme Coins
    "DOGE": "dogecoin", # <-- ADDED
    "SHIB": "shiba-inu",
    "PEPE": "pepe", 
    "WIF": "dogwifhat", 
    "BONK": "bonk",
    "FLOKI": "floki"
}

# import this to access metadata

# --- Direction control setup ---
TRADE_DIRECTION_CHANCE = 0.25  # 25% of trades will be SELL

def determine_direction(roi, simulated=True):
    """Auto determine BUY or SELL based on ROI / random flip for simulated trades."""
    if simulated:
        # About 25% of simulated trades will be SELL
        if random.random() < TRADE_DIRECTION_CHANCE:
            roi = -abs(roi)
            direction = "SELL"
        else:
            roi = abs(roi)
            direction = "BUY"
    else:
        direction = "BUY" if roi >= 0 else "SELL"
    return roi, direction

def generate_entry_exit(symbol, roi, live_price=None):
    """
    Generate realistic entry & exit prices for any symbol.
    If live_price is provided (from get_market_data), reuse it as the exit price.
    For stocks: uses yfinance.
    For crypto: uses Coinbase, falls back to CoinGecko.
    For NIKY/DEW: simulated prices.
    """
    symbol_upper = symbol.upper()

    try:
        # 🟢 Use live price if provided
        if live_price is not None:
            exit_price = round(float(live_price), 6)  # ✅ real, live exit
        else:
            # 🟢 STOCKS → use yfinance
            if symbol_upper in STOCK_SYMBOLS:
                stock = yf.Ticker(symbol_upper)
                live_price = stock.info.get("regularMarketPrice")
                if not live_price:
                    live_price = stock.history(period="1d")["Close"].iloc[-1]
                exit_price = round(float(live_price), 6)
            # 🟢 CRYPTO → try Coinbase first, then CoinGecko
            elif symbol_upper in CRYPTO_SYMBOLS:
                try:
                    # Coinbase API
                    url = f"https://api.coinbase.com/v2/prices/{symbol_upper}-USD/spot"
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200 and "data" in r.json():
                        exit_price = round(float(r.json()["data"]["amount"]), 6)
                    else:
                        raise Exception("Coinbase API failed")
                except Exception as e:
                    logger.warning(f"⚠️ Coinbase failed for {symbol_upper}: {e}, falling back to CoinGecko")
                    cg_id = CRYPTO_ID_MAP.get(symbol_upper)
                    if cg_id:
                        data = cg.get_price(ids=cg_id, vs_currencies="usd")
                        exit_price = round(float(data[cg_id]["usd"]), 6)
                    else:
                        raise Exception("No CoinGecko ID mapped")
            # 🟢 MEME COINS (NIKY, DEW) → simulated
            elif symbol_upper in ["NIKY", "DEW"]:
                exit_price = round(random.uniform(0.0001, 0.05), 6)
            # 🟡 Generic fallback
            else:
                exit_price = round(random.uniform(1, 500), 6)

        # 🟢 Compute fake entry based on ROI
        entry_price = round(exit_price / (1 + roi / 100.0), 6)  # ✅ fake entry
        return entry_price, exit_price

    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch entry/exit for {symbol}: {e}")
        exit_price = round(random.uniform(1, 500), 6)
        entry_price = round(exit_price / (1 + roi / 100.0), 6)
        return entry_price, exit_price


def pick_broker_for_symbol(symbol):
    """Return a realistic broker/exchange name depending on symbol type."""
    s = symbol.upper()
    if s in STOCK_SYMBOLS:
        return random.choice(["Robinhood", "Webull", "E*TRADE", "Charles Schwab", "Fidelity"])
    elif s in CRYPTO_SYMBOLS:
        return random.choice(["Binance", "Coinbase", "Kraken", "Bybit", "OKX", "Bitget"])
    elif s in MEME_COINS:
        return random.choice(["Uniswap", "Raydium", "PancakeSwap", "Jupiter", "DEXTools"])
    else:
        return "Verified Exchange"
      
      
def init_traders_if_needed():
    """Ensure traders table has at least basic sample users after reset."""
    from models import users
    with engine.begin() as conn:
        existing = conn.execute(select(users)).fetchall()
        if not existing:
            for _, name in random.sample(RANKING_TRADERS, 10):
                conn.execute(users.insert().values(
                    user_id=str(random.randint(1000,9999)),
                    username=name.lower().replace(" ", "_"),
                    display_name=name,
                    wins=0,
                    total_trades=0,
                    total_profit=0
                ))
    logger.info("✅ Traders initialized successfully.")

def save_trade_log(
    txid, symbol, trader_name, deposit, profit, roi, strategy, reason,
    entry_price=None, exit_price=None, quantity=None, commission=None, slippage=None, direction=None
):
    """Save each posted trade to the database with realistic execution metrics and correct broker mapping."""
    try:
        symbol_upper = symbol.upper()

        # --- Smart Broker Mapping (realistic by asset type) ---
        if symbol_upper in STOCK_SYMBOLS:
            broker_name = random.choice([
                "Robinhood", "Webull", "E*TRADE", "Charles Schwab", "Fidelity"
            ])
        elif symbol_upper in CRYPTO_SYMBOLS:
            broker_name = random.choice([
                "Binance", "Coinbase", "Kraken", "Bybit", "OKX", "Bitget"
            ])
        elif symbol_upper in MEME_COINS:
            broker_name = random.choice([
                "Uniswap", "Raydium", "PancakeSwap", "Jupiter", "DEXTools"
            ])
        else:
            broker_name = "Verified Exchange"

        # --- Generate or reuse values if not provided ---
        entry_price = entry_price or round(random.uniform(10, 350), 4)
        exit_price = exit_price or round(entry_price * (1 + roi / 100), 4)
        quantity = quantity or round(deposit / entry_price, 6)
        total_value_exit = round(quantity * exit_price, 2)
        commission = commission or round(deposit * 0.001, 2)          # 0.1% fee
        slippage = slippage or round(random.uniform(0.01, 0.15), 4)   # 0.01–0.15%
        

        # --- Insert into DB ---
        with engine.begin() as conn:
            conn.execute(
                trade_logs.insert().values(
                    txid=txid,
                    symbol=symbol_upper,
                    trader_name=trader_name,
                    deposit=round(deposit, 2),
                    profit=round(profit, 2),
                    roi=round(roi, 2),
                    strategy=strategy,
                    reason=reason,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    total_value_exit=total_value_exit,
                    commission=commission,
                    slippage=slippage,
                    direction=direction,
                    broker_name=broker_name,
                    posted_at=datetime.now(timezone.utc)
                )
            )

        # --- Logging ---
        logger.info(
            f"✅ Trade saved: {txid} | {symbol_upper} | {broker_name} | "
            f"PnL {profit:+.2f} | ROI {roi:+.2f}% | Entry {entry_price} | Exit {exit_price} | Qty {quantity}"
        )

    except Exception as e:
        logger.error(f"⚠️ Failed to save trade log {txid}: {e}", exc_info=True)

import requests

# =========================
# 🔧 UNIVERSAL SYMBOL RESOLVER
# =========================
def resolve_symbol_for_exchanges(symbol: str):
    """
    Maps crypto or memecoin symbols to correct identifiers
    for Binance, Bybit, CoinGecko, and DEX (Raydium/PancakeSwap/Burger).
    Skips simulated-only coins (NIKY, DEW).
    """
    s = symbol.upper().strip()

    # Skip fake coins
    if s in ["NIKY", "DEW"]:
        return {
            "symbol": s,
            "binance": None,
            "bybit": None,
            "coingecko": None,
            "dex_pair": None,
            "source": "simulated"
        }

    # Binance + Bybit use same pair format (BASE+USDT)
    binance_symbol = f"{s}USDT"
    bybit_symbol = f"{s}USDT"

    # CoinGecko mapping
    coingecko_id = CRYPTO_ID_MAP.get(s)
    if not coingecko_id:
        coingecko_id = {
            "WIF": "dogwifhat",
            "BONK": "bonk",
            "SHIB": "shiba-inu",
            "DOGE": "dogecoin",
            "PEPE": "pepe",
            "SUI": "sui",
            "MATIC": "matic-network",
            "AVAX": "avalanche-2",
            "XRP": "ripple",
            "ADA": "cardano",
            "XLM": "stellar",
            "PHNTM": "phantom",
        }.get(s, s.lower())

    # DEX pair mapping (for fallback)
    if s in ["WIF", "BONK", "PHNTM", "RAY", "SOL", "SUI"]:
        dex_pair = f"{s}/SOL"
        dex_platform = "Raydium"
    elif s in ["DOGE", "SHIB", "PEPE", "FLOKI", "CAKE", "BURGER"]:
        dex_pair = f"{s}/BNB"
        dex_platform = "PancakeSwap"
    else:
        dex_pair = f"{s}/USDT"
        dex_platform = "Generic DEX"

    return {
        "symbol": s,
        "binance": binance_symbol,
        "bybit": bybit_symbol,
        "coingecko": coingecko_id,
        "dex_pair": dex_pair,
        "dex_platform": dex_platform,
        "source": "auto"
    }

# =========================
# 🌐 MARKET DATA FETCHER (AUTO SOURCE)
# =========================
def get_market_data(symbol):
    """
    Attempts live price data in order:
      1️⃣ Binance → 2️⃣ Bybit → 3️⃣ CoinGecko → 4️⃣ DEX fallback
    Returns tuple: (current_price, price_24h_ago, %change_24h)
    """
    sym_map = resolve_symbol_for_exchanges(symbol)
    s = sym_map["symbol"]

    if sym_map["source"] == "simulated":
        logger.info(f"🎭 {s} is a simulated token (skipping real API).")
        base_price = random.uniform(0.001, 0.05)
        pct_change = random.uniform(-5, 15)
        return (base_price, base_price / (1 + pct_change / 100), pct_change)

    # ------------------------
    # 1️⃣ Binance API
    # ------------------------
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={sym_map['binance']}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200 and "lastPrice" in r.json():
            data = r.json()
            last_price = float(data["lastPrice"])
            pct_change = float(data["priceChangePercent"])
            open_price = last_price / (1 + pct_change / 100)
            logger.info(f"📊 Binance → {s} @ ${last_price:.4f} ({pct_change:+.2f}%)")
            return (last_price, open_price, pct_change)
        else:
            logger.warning(f"🔁 Binance failed for {s}, falling back...")
    except Exception as e:
        logger.warning(f"⚠️ Binance API error for {s}: {e}")

    # ------------------------
    # 2️⃣ Bybit API
    # ------------------------
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym_map['bybit']}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200 and r.json().get("result", {}).get("list"):
            ticker = r.json()["result"]["list"][0]
            last_price = float(ticker["lastPrice"])
            pct_change = float(ticker.get("price24hPcnt", 0)) * 100
            open_price = last_price / (1 + pct_change / 100)
            logger.info(f"📈 Bybit → {s} @ ${last_price:.4f} ({pct_change:+.2f}%)")
            return (last_price, open_price, pct_change)
        else:
            logger.warning(f"🔁 Bybit failed for {s}, falling back...")
    except Exception as e:
        logger.warning(f"⚠️ Bybit API error for {s}: {e}")

    # ------------------------
    # 3️⃣ CoinGecko API
    # ------------------------
    try:
        if sym_map["coingecko"]:
            data = cg.get_price(ids=sym_map["coingecko"], vs_currencies="usd")
            if sym_map["coingecko"] in data:
                price = float(data[sym_map["coingecko"]]["usd"])
                pct_change = random.uniform(-3, 3)
                open_price = price / (1 + pct_change / 100)
                logger.info(f"🦎 CoinGecko → {s} @ ${price:.4f} ({pct_change:+.2f}%)")
                return (price, open_price, pct_change)
        logger.warning(f"🔁 CoinGecko failed for {s}, falling back...")
    except Exception as e:
        logger.warning(f"⚠️ CoinGecko API error for {s}: {e}")

    # ------------------------
    # 4️⃣ DEX / SIMULATED FALLBACK
    # ------------------------
    base_price = random.uniform(0.0001, 50)
    pct_change = random.uniform(-10, 15)
    open_price = base_price / (1 + pct_change / 100)
    logger.info(f"🧩 DEX fallback → {s} ({sym_map['dex_platform']}) @ ${base_price:.4f} ({pct_change:+.2f}%)")
    return (base_price, open_price, pct_change)
# ✅ Track last posted category (so posts rotate properly)
last_category = None
# ===============================
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
import numpy as np # Make sure 'import numpy as np' is at the top of your script

def generate_profit_scenario(symbol: str):
    """
    Generates a realistic simulated trade scenario.
    Returns: deposit, profit, roi, reason, trading_style, direction
    """
    symbol = (symbol or "").upper()

    # 🎯 Deposit range by type
    if symbol in MEME_COINS:
        deposit = random.randint(200, 7500)
    elif symbol in CRYPTO_SYMBOLS:
        deposit = random.randint(500, 10500)
    else:  # stocks
        deposit = random.randint(1000, 12000)

    # 🎲 Decide win or loss bias
    win_trade = random.random() < 0.9  # 90% chance win

    if win_trade:
        if symbol in MEME_COINS:
            roi = round(random.uniform(30, 700), 2)
        elif symbol in CRYPTO_SYMBOLS:
            roi = round(random.uniform(10, 300), 2)
        else:
            roi = round(random.uniform(5, 120), 2)
    else:
        roi = round(random.uniform(-25, -5), 2)

    # 💰 Calculate profit or loss
    profit = round(deposit * (roi / 100.0), 2)

    # 🧭 Direction (LONG/SHORT)
    direction = "Bullish" if roi >= 0 else "Bearish"

    # 📊 Trading style
    trading_styles = [
        "Momentum Reversal", "Scalp Strategy", "Swing Entry",
        "Breakout Play", "Pullback Setup", "News Catalyst",
        "Range Compression", "Market Analysis", "Dip Buy Setup"
    ]
    trading_style = random.choice(trading_styles)

    # 💬 Reason message
    if roi >= 0:
        reason = random.choice([
            "Capitalized on strong breakout momentum.",
            "Executed near perfect dip entry before rebound.",
            "Followed institutional flow; profit locked.",
            "High-volume move aligned with RSI confirmation.",
            "Used call options to leverage bullish continuation."
        ])
    else:
        reason = random.choice([
            "Stop-loss triggered after failed breakout.",
            "Bearish engulfing invalidated trade setup.",
            "Unexpected news event caused downside gap.",
            "Short-term reversal hit tight stop levels.",
            "Tight stop triggered; trade closed in red."
        ])

    return deposit, profit, roi, reason, trading_style, direction
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

# ================================
# NEW MEMBER WELCOME HANDLER
# ================================
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a personalized welcome message to new members, then delete after a delay."""
    try:
        for member in update.message.new_chat_members:
            name = member.first_name or member.username or "Trader"

            # 👋 Welcome message
            welcome_text = (
                f"👋 Welcome <b>{name}</b>!\n\n"
                f"You’ve joined <b>Profit Flex Group</b> , where verified profit drops from "
                f"<b>Options Trading University</b> are posted live. 💸\n\n"
                f"👉 Stay tuned for real-time profit updates, leaderboard movements, "
                f"and inspiration from top traders worldwide.\n\n"
                f"<i>(This message will disappear automatically to keep the chat clean.)</i>"
            )

            sent_msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=welcome_text,
                parse_mode=constants.ParseMode.HTML
            )

            # ⏳ Auto delete after 20 seconds (adjustable)
            await asyncio.sleep(20)
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=sent_msg.message_id)
            except Exception:
                pass  # Ignore if message already deleted or permissions missing

    except Exception as e:
        logger.error(f"⚠️ Welcome message error: {e}")
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
    Save top 10 traders to DB with medals, consistent formatting,
    and clean numeric display (no floats or weird decimals).
    """
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []

    for i, (name, total) in enumerate(parsed, start=1):
        # Ensure integer display with comma separation
        clean_total = int(round(total))
        badge = medals.get(i, f"{i}.")
        lines.append(f"{badge} {name} — ${clean_total:,} profit")

    # ✅ Always overwrite the previous cache
    with engine.begin() as conn:
        conn.execute(delete(rankings_cache))
        conn.execute(insert(rankings_cache).values(
            content="\n".join(lines),
            timestamp=datetime.now(timezone.utc)
        ))

    logger.info("🏆 Leaderboard saved successfully.")
    return lines


def update_rankings_with_new_profit(trader_name, new_profit):
    """
    Update leaderboard cumulative totals.
    Ensures numbering, medals, and rounding are consistent.
    """
    parsed = fetch_cached_rankings()
    clean = []

    # 🧹 Parse the existing rankings cleanly
    for line in parsed:
        try:
            # Remove medals, numbers, and emojis
            raw = line.split("—")[0].strip()
            raw = raw.replace("🥇", "").replace("🥈", "").replace("🥉", "")
            raw = "".join([c for c in raw if not c.isdigit() and c not in "."])  # strip stray dots or digits
            name = raw.strip()

            # Extract numeric part safely
            profit_str = line.split("$")[-1].split()[0].replace(",", "")
            profit = int(float(profit_str))
            clean.append((name, profit))
        except:
            continue

    # 🧩 If no valid data, seed a fresh board
    if not clean:
        selected = random.sample(RANKING_TRADERS, 10)
        clean = [(name, random.randint(2000, 8000)) for _, name in selected]

    # 🧮 Update or add trader (rounded to nearest whole number)
    found = False
    for i, (name, total) in enumerate(clean):
        if name == trader_name:
            clean[i] = (trader_name, round(total + new_profit))
            found = True
            break
    if not found:
        clean.append((trader_name, round(new_profit)))

    # 🏆 Sort and keep top 10
    clean.sort(key=lambda x: x[1], reverse=True)
    clean = clean[:10]

    # 🥇 Format output cleanly
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for i, (name, total) in enumerate(clean, start=1):
        badge = medals.get(i, f"{i}.")
        # 👇 Always show as integer dollars
        lines.append(f"{badge} {name} — ${int(total):,} profit")

    # 💾 Save updated rankings to DB
    with engine.begin() as conn:
        conn.execute(delete(rankings_cache))
        conn.execute(insert(rankings_cache).values(
            content="\n".join(lines),
            timestamp=datetime.now(timezone.utc)
        ))

    # 🎯 Return leaderboard + trader’s position
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
import requests # Used to download a professional font

# --- Helper function to get a good font (same as before) ---
def get_font(size, weight="Regular"):
    """Downloads and loads the 'Inter' font from Google Fonts."""
    font_name = "Inter"
    url = f"https://rsms.me/inter/font-files/Inter-{weight}.otf"
    try:
        font_file = f"Inter-{weight}.otf"
        with open(font_file, "rb") as f:
            return ImageFont.truetype(f, size)
    except FileNotFoundError:
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(font_file, "wb") as f:
                f.write(response.content)
            return ImageFont.truetype(io.BytesIO(response.content), size)
        except requests.exceptions.RequestException:
            print("Warning: Could not download font. Using default.")
            return ImageFont.load_default()

def generate_profit_card(symbol, profit, roi, deposit, trader_name="TraderX"):
    """
    Generate a wide, dashboard-style profit report image with a bar chart.
    Returns an in-memory PNG buffer.
    """
    W, H = 1200, 400 # Wide banner dimensions

    # --- 1. Colors & Fonts based on your image ---
    BG_COLOR = (12, 12, 12) # Very dark grey, almost black
    TEXT_COLOR = (240, 240, 240)
    PROFIT_COLOR = (29, 255, 178) # Vibrant mint green
    ROI_COLOR = (255, 228, 0) # Bright yellow
    TRADER_COLOR = (59, 130, 246) # Clear blue

    # Determine profit/loss color and prefix
    if profit >= 0:
        actual_profit_color = PROFIT_COLOR
        profit_prefix = "+"
    else:
        actual_profit_color = "#ef4444" # Red for loss
        profit_prefix = ""

    # Load fonts
    font_title = get_font(32, "Bold")
    font_data = get_font(28, "Medium")

    # --- 2. Setup Canvas ---
    bg = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(bg)

    # --- 3. Draw Left Column (Text Info) ---
    pad_x = 50
    y = 60
    line_spacing = 65

    # Title with icon
    draw.text((pad_x, y), "□", fill=TEXT_COLOR, font=font_title)
    draw.text((pad_x + 40, y), f"{symbol} Profit Report", fill=TEXT_COLOR, font=font_title)
    y += line_spacing * 1.5

    # Helper to draw a line of text with a colored value
    def draw_info_line(label, value, value_color):
        nonlocal y
        # Draw the label (e.g., "Profit: ")
        draw.text((pad_x, y), label, fill=TEXT_COLOR, font=font_data)
        # Get width of the label to position the value right after it
        label_width = draw.textlength(label, font=font_data)
        # Draw the value
        draw.text((pad_x + label_width, y), value, fill=value_color, font=font_data)
        y += line_spacing

    # Draw each data point
    draw_info_line("Deposit: ", f"${deposit:,.0f}", TEXT_COLOR)
    draw_info_line("Profit: ", f"{profit_prefix}${abs(profit):,.0f}", actual_profit_color)
    draw_info_line("ROI: ", f"{roi:.1f}%", ROI_COLOR)
    draw_info_line("Trader: ", trader_name, TRADER_COLOR)

    # --- 4. Draw Right Column (Bar Chart) ---
    chart_area_x = 600
    chart_area_y = 60
    chart_area_w = W - chart_area_x - pad_x
    chart_area_h = H - chart_area_y * 2

    num_bars = 12
    bar_spacing = 15
    bar_width = (chart_area_w - (bar_spacing * (num_bars - 1))) / num_bars

    for i in range(num_bars):
        # Generate a random height for each bar for visual effect
        bar_height = chart_area_h * random.uniform(0.15, 0.95)
        
        x0 = chart_area_x + i * (bar_width + bar_spacing)
        y0 = chart_area_y + (chart_area_h - bar_height)
        x1 = x0 + bar_width
        y1 = chart_area_y + chart_area_h
        
        draw.rectangle([x0, y0, x1, y1], fill=PROFIT_COLOR)

    # --- 5. Save to Buffer ---
    buf = io.BytesIO()
    bg.save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf

# --- Example Usage ---
if __name__ == '__main__':
    # Generate a card using data similar to your example
    profit_banner_buffer = generate_profit_card(
        symbol="BTC",
        profit=8450,
        roi=604.2,
        deposit=1400, # Calculated from profit and ROI
        trader_name="Robert Garcia"
    )
    with open("btc_profit_banner.png", "wb") as f:
        f.write(profit_banner_buffer.getbuffer())
    print("Generated 'btc_profit_banner.png'")

    # Generate a second example for a different stock
    stock_banner_buffer = generate_profit_card(
        symbol="NVDA",
        profit=21550,
        roi=43.1,
        deposit=50000,
        trader_name="Jane Doe"
    )
    with open("nvda_profit_banner.png", "wb") as f:
        f.write(stock_banner_buffer.getbuffer())
    print("Generated 'nvda_profit_banner.png'")

# ======================
# Short caption fallback
# ======================
def short_highlight(symbol: str, profit: float, roi: float) -> str:
    return f"+${profit:,.0f} on {symbol} • ROI {roi:.1f}% 🔥"

# ======================
# ======================

ADMIN_ID = os.getenv("ADMIN_ID")

# ===============================
# 🔧 Profit/Loss Label Helper
# ===============================
def profit_status_labels(profit: float):
    """
    Returns emoji and label depending on profit sign.
    Example:
        +500 -> ("✅", "Profit")
        -200 -> ("❌", "Loss")
    """
    if profit >= 0:
        return "✅", "Profit"
    else:
        return "❌", "Loss"
      

# ===============================
# AUTO PROFIT POSTING LOOP (REAL + SIMULATED FIX)
# ===============================
async def profit_posting_loop(app):
    logger.info("🚀 Profit posting loop started (70% simulated / 30% real).")
    while True:
        try:
            # Random wait between posts
            sleep_time = random.randint(15, 40) * 60
            use_simulated = random.random() < 0.7  # 70% simulated
            all_symbols = STOCK_SYMBOLS + CRYPTO_SYMBOLS + MEME_COINS
            symbol = random.choice(all_symbols)

            for attempt in range(5):
                # 🔹 Try to fetch live market data
                try:
                    current_price, price_24h_ago, pct_change_24h = get_market_data(symbol)
                    exit_price = round(float(current_price), 6)  # ✅ real, live exit
                except Exception:
                    exit_price = round(random.uniform(1, 500), 6)  # fallback

                if not use_simulated and abs(pct_change_24h) >= 0.2:
                    # Real trade mode
                    deposit = random.randint(500, 5000)
                    roi = pct_change_24h
                    profit = round(deposit * (roi / 100.0), 2)
                    entry_price = round(exit_price / (1 + roi / 100.0), 6)  # ✅ fake entry
                    direction = "Bullish" if roi >= 0 else "Bearish"
                    reason = f"Capitalized on {pct_change_24h:+.2f}% 24h move."
                    trading_style = "Market Analysis"
                    post_title = f"📈 <b>{symbol} Live Market Report</b>"
                    break
                else:
                    use_simulated = True

                if use_simulated:
                    deposit, profit, roi, reason, trading_style, direction = generate_profit_scenario(symbol)
                    entry_price = round(exit_price / (1 + roi / 100.0), 6)  # ✅ fake entry
                    post_title = f"🎯 <b>{symbol} Live Market Report</b>"
                    break
            else:
                logger.warning("All attempts failed — retrying soon.")
                await asyncio.sleep(10)
                continue

            # Derived metrics
            quantity = round(deposit / entry_price, 6)
            commission = round(deposit * 0.001, 2)
            slippage = round(random.uniform(0.01, 0.15), 4)

            trader_name = random.choice(RANKING_TRADERS)[1]
            rankings, pos = update_rankings_with_new_profit(trader_name, profit)
            txid = generate_unique_txid(engine)
            log_url = f"{WEBSITE_URL.rstrip('/')}/log/{txid}"

            save_trade_log(
                txid=txid, symbol=symbol, trader_name=trader_name,
                deposit=deposit, profit=profit, roi=roi, strategy=trading_style,
                reason=reason, entry_price=entry_price, exit_price=exit_price,
                quantity=quantity, commission=commission, slippage=slippage, direction=direction
            )

            # ✅ FIXED indentation (was too deep before)
            status_emoji, profit_label = profit_status_labels(profit)

            msg = (
                f"{post_title}\n"
                f"👤 Trader: <b>{trader_name}</b>\n"
                f"💰 Deposit: <b>${deposit:,.2f}</b>\n"
                f"{status_emoji} <b>{profit_label}:</b> <b>${abs(profit):,.2f}</b> (<b>{roi:+.2f}%</b>)\n"
                f"📊 Entry: <b>${entry_price}</b> | Exit: <b>${exit_price}</b>\n"
                f"📦 Qty: <b>{quantity}</b> | Comm: <b>${commission}</b> | Slip: <b>{slippage}%</b>\n"
                f"🔥 Strategy: <b>{trading_style}</b> — {reason}\n\n"
                f"🏆 <b>Leaderboard (Top 10)</b>\n" + "\n".join(rankings) + "\n\n"
                f"<a href='{log_url}'>Trade execution validated via broker statement (TX#{txid})</a>\n\n"
                f"💎 <b>Powered by Options Trading University</b>"
            )

            img_buf = generate_profit_card(symbol, profit, roi, deposit, trader_name)
            await app.bot.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                photo=img_buf,
                caption=msg,
                parse_mode=constants.ParseMode.HTML
            )

            logger.info(f"✅ Posted {symbol} ({'Simulated' if use_simulated else 'Real'}) — next in {sleep_time/60:.1f} min")
            await asyncio.sleep(sleep_time)

        except Exception as e:
            logger.error(f"Error in posting loop: {e}", exc_info=True)
            await asyncio.sleep(60)
# ===============================
# MANUAL POST HANDLER (REAL + SIMULATED FIX)
# ===============================
async def manual_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID):
        await update.message.reply_text("🚫 Unauthorized.")
        return

    await update.message.reply_text("⏳ Generating manual trade report...")

    try:
        symbol = random.choice(STOCK_SYMBOLS + CRYPTO_SYMBOLS + MEME_COINS)
        use_simulated = random.random() < 0.7

        for attempt in range(5):
            # 🔹 Try to fetch live market data
            try:
                current_price, price_24h_ago, pct_change_24h = get_market_data(symbol)
                exit_price = round(float(current_price), 6)  # ✅ real, live exit
            except Exception:
                exit_price = round(random.uniform(1, 500), 6)  # fallback

            if not use_simulated and abs(pct_change_24h) >= 0.2:
                # Real trade mode
                deposit = random.randint(500, 5000)
                roi = pct_change_24h
                profit = round(deposit * (roi / 100.0), 2)
                entry_price = round(exit_price / (1 + roi / 100.0), 6)  # ✅ fake entry
                direction = "Bullish" if roi >= 0 else "Bearish"
                reason = f"Capitalized on {pct_change_24h:+.2f}% 24h move."
                trading_style = "Market Analysis"
                post_title = f"📈 <b>{symbol} Live Market Report</b>"
                break
            else:
                use_simulated = True

            if use_simulated:
                deposit, profit, roi, reason, trading_style, direction = generate_profit_scenario(symbol)
                entry_price = round(exit_price / (1 + roi / 100.0), 6)  # ✅ fake entry
                post_title = f"🎯 <b>{symbol} Live Market Report</b>"
                break
        else:
            await update.message.reply_text("⚠️ Failed to fetch data.")
            return

        quantity = round(deposit / entry_price, 6)
        commission = round(deposit * 0.001, 2)
        slippage = round(random.uniform(0.01, 0.15), 4)

        trader_name = random.choice(RANKING_TRADERS)[1]
        rankings, _ = update_rankings_with_new_profit(trader_name, profit)
        txid = generate_unique_txid(engine)
        log_url = f"{WEBSITE_URL.rstrip('/')}/log/{txid}"

        save_trade_log(
            txid=txid, symbol=symbol, trader_name=trader_name,
            deposit=deposit, profit=profit, roi=roi, strategy=trading_style,
            reason=reason, entry_price=entry_price, exit_price=exit_price,
            quantity=quantity, commission=commission, slippage=slippage, direction=direction
        )

        # ✅ FIXED indentation (was causing error)
        status_emoji, profit_label = profit_status_labels(profit)

        msg = (
            f"{post_title}\n"
            f"👤 Trader: <b>{trader_name}</b>\n"
            f"💰 Deposit: <b>${deposit:,.2f}</b>\n"
            f"{status_emoji} <b>{profit_label}:</b> <b>${abs(profit):,.2f}</b> (<b>{roi:+.2f}%</b>)\n"
            f"📊 Entry: <b>${entry_price}</b> | Exit: <b>${exit_price}</b>\n"
            f"📦 Qty: <b>{quantity}</b> | Comm: <b>${commission}</b> | Slip: <b>{slippage}%</b>\n"
            f"🔥 Strategy: <b>{trading_style}</b> — {reason}\n\n"
            f"🏆 <b>Leaderboard (Top 10)</b>\n" + "\n".join(rankings) + "\n\n"
            f"<a href='{log_url}'>Trade execution validated via broker statement (TX#{txid})</a>\n\n"
            f"💎 <b>Powered by Options Trading University</b>"
        )

        img_buf = generate_profit_card(symbol, profit, roi, deposit, trader_name)
        await context.bot.send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            photo=img_buf,
            caption=msg,
            parse_mode=constants.ParseMode.HTML
        )
        await update.message.reply_text(f"✅ Manual post for {symbol} sent successfully!")

    except Exception as e:
        logger.error(f"Manual post error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Failed: {e}")


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
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    # Hook startup event
    app.post_init = on_startup

    logger.info("🚀 Bot application built and ready.")
    app.run_polling()

# Run main
if __name__ == "__main__":
    main()
