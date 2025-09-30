"""
Profit flex bot for stocks, crypto, and $NIKY meme coin on Solana.
Posts non-repetitive profit scenarios every 20/40 minutes with tailored ranges:
- Stocks/Crypto: $209 → $1,000, $509 → $4,000, etc. (2x–8x, 100%–700% gains).
- $NIKY: $309 → $700, $700 → $5k–$7k, $1,000 → $11,000, etc. (2x–15x, 100%–1400% gains).
Varied messaging with multiple templates and reasons to avoid repetition.
"""

import os
import random
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine
from telegram import Bot, Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Setup logging
logging.basicConfig(
    filename='profit_flex_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

TELEGRAM_TOKEN = os.getenv(8424414707:AAE8l6_6krko6LapUOAU5U8LhSzjP_TRT20)
TELEGRAM_CHAT_ID = os.getenv(-1003118326700)
STOCK_SYMBOLS = [s.strip() for s in os.getenv("STOCK_SYMBOLS", "TSLA,AAPL,NVDA,MSFT,AMZN,GOOGL,META").split(",")]
CRYPTO_SYMBOLS = [s.strip() for s in os.getenv("CRYPTO_SYMBOLS", "BTC,ETH,SOL").split(",")]
MEME_COIN = "NIKY"  # Onyx Dachshund on Solana
SWING_TRADE_INTERVAL_MINUTES = int(os.getenv("SWING_TRADE_INTERVAL_MINUTES", "20"))  # 20 or 40
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///profit_flex.db")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://optionstradinguni.online/")
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "5"))

# Combine symbols for flex posts
ALL_SYMBOLS = STOCK_SYMBOLS + CRYPTO_SYMBOLS + [MEME_COIN]

# Initialize DB engine
engine = create_engine(DATABASE_URL, future=True)

# Telegram Bot instance
bot = Bot(token=TELEGRAM_TOKEN)

# Helper: Fetch recent profits from DB to avoid repetition
def fetch_recent_profits():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT profit FROM posts WHERE profit IS NOT NULL ORDER BY posted_at DESC LIMIT 50", conn)
            return set(df['profit'].tolist())
    except Exception as e:
        logger.error(f"Error fetching recent profits: {e}")
        return set()

# Helper: Generate profit flex scenario with non-repetitive profits
def generate_flex_scenario(symbol):
    recent_profits = fetch_recent_profits()
    
    if symbol == MEME_COIN:
        deposit_options = [
            (309, 700),  # $309 → $700
            (700, random.choice([5000, 6000, 7000])),  # $700 → $5k/$6k/$7k
            (1000, 11000),  # $1,000 → $11,000
            (1500, random.randint(8000, 22000)),  # $1,500 → $8k–$22k
        ]
        max_attempts = 10
        for _ in range(max_attempts):
            deposit, target_profit = random.choice(deposit_options)
            if target_profit not in recent_profits:
                break
        else:
            deposit = 1500
            target_profit = random.randint(8000, 22000)
            while target_profit in recent_profits:
                target_profit = random.randint(8000, 22000)
        multiplier = target_profit / deposit
        percentage_gain = round((multiplier - 1) * 100, 1)
        price_increase = int(percentage_gain * random.uniform(0.8, 1.2))  # Align pump with gain
        trading_style = random.choice(["Early Sniping", "Pump Riding", "Community Flip", "Airdrop Hunt"])
        reasons = [
            f"$NIKY exploded {price_increase}% after a viral dachshund meme!",
            f"Solana mooned, $NIKY up {price_increase}% on Raydium hype!",
            f"Onyx Dachshund gang flipped $NIKY for a {price_increase}% pump!",
            f"$NIKY soared {price_increase}% on meme coin madness!",
            f"Sniped $NIKY’s {price_increase}% spike like a pro!",
            f"$NIKY’s {price_increase}% pump was a meme coin masterclass!",
            f"Caught $NIKY’s {price_increase}% wave on Solana!",
            f"$NIKY went ballistic with a {price_increase}% surge!",
            f"Dachshund vibes sent $NIKY up {price_increase}%!",
            f"$NIKY’s {price_increase}% moonshot was pure fire!",
        ]
    else:  # Stocks or Crypto
        deposit_options = [
            (209, 1000),  # $209 → $1,000
            (509, 4000),  # $509 → $4,000
            (500, random.randint(1200, 5000)),  # $500 → $1.2k–$5k
            (1000, random.randint(2500, 8000)),  # $1,000 → $2.5k–$8k
        ]
        max_attempts = 10
        for _ in range(max_attempts):
            deposit, target_profit = random.choice(deposit_options)
            if target_profit not in recent_profits:
                break
        else:
            deposit = 500
            target_profit = random.randint(1200, 5000)
            while target_profit in recent_profits:
                target_profit = random.randint(1200, 5000)
        multiplier = target_profit / deposit
        percentage_gain = round((multiplier - 1) * 100, 1)
        price_increase = int(percentage_gain * random.uniform(0.8, 1.2))  # Align pump with gain
        if symbol in STOCK_SYMBOLS:
            trading_style = random.choice(["Scalping", "Day Trading", "Swing Trade", "Position Trade"])
            reasons = [
                f"{symbol} {trading_style} skyrocketed {price_increase}% in a market rally!",
                f"Nailed a {price_increase}% pump with {trading_style} on {symbol}!",
                f"{symbol} surged {price_increase}% on {trading_style} vibes!",
                f"Wall Street went wild: {symbol} up {price_increase}% in {trading_style}!",
                f"{trading_style} on {symbol} crushed it with a {price_increase}% banger!",
                f"{symbol} {trading_style} popped off for {price_increase}% gains!",
                f"Locked in a {price_increase}% win on {symbol} with {trading_style}!",
                f"{symbol}’s {price_increase}% spike was a {trading_style} masterpiece!",
                f"{trading_style} on {symbol} brought a {price_increase}% haul!",
                f"{symbol} mooned {price_increase}% with {trading_style} swagger!",
            ]
        else:  # CRYPTO_SYMBOLS
            trading_style = random.choice(["HODL", "Swing Trade", "DCA", "Arbitrage", "Leverage Trading"])
            reasons = [
                f"{symbol} {trading_style} mooned {price_increase}% on crypto hype!",
                f"{trading_style} on {symbol} smashed a {price_increase}% pump!",
                f"{symbol} soared {price_increase}% in a {trading_style} frenzy!",
                f"Crypto {trading_style} vibes sent {symbol} up {price_increase}%!",
                f"Locked in a {price_increase}% gain on {symbol} with {trading_style}!",
                f"{symbol} {trading_style} delivered a {price_increase}% jackpot!",
                f"{trading_style} on {symbol} was a {price_increase}% crypto win!",
                f"{symbol} pumped {price_increase}% with {trading_style} finesse!",
                f"Crypto {trading_style} on {symbol} scored a {price_increase}% banger!",
                f"{symbol}’s {price_increase}% surge was pure {trading_style} gold!",
            ]
    
    return deposit, target_profit, percentage_gain, random.choice(reasons), trading_style

# Helper: Fetch user stats from DB
def fetch_user_stats():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT username, wins, total_trades, round((wins * 1.0 / total_trades) * 100, 1) as win_rate FROM users ORDER BY RANDOM() LIMIT 3", conn)
            return df
    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        return pd.DataFrame()

# Craft a profit flex message
def craft_flex_message(symbol, deposit, profit, percentage_gain, reason, trading_style):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    multiplier = round(profit / deposit, 1)
    user_df = fetch_user_stats()
    social_lines = []
    for _, r in user_df.iterrows():
        social_lines.append(f"{r['username']} — {r['wins']}/{r['total_trades']} trades • {r['win_rate']}% win rate")
    if user_df.empty:
        social_lines = [f"Trader_{random.randint(1000,9999)} — {random.randint(10,50)} trades • {round(random.uniform(60,95),1)}% success" for _ in range(3)]
    
    social_text = "\n".join(social_lines)
    tag = "#NIKY #SolanaMeme #Moon" if symbol == "NIKY" else "#TradingSuccess #Moon"
    asset_desc = "Onyx Dachshund (Solana)" if symbol == "NIKY" else symbol
    templates = [
        (
            f"💎 <b>{symbol} PROFIT FLEX</b> 🚀\n"
            f"<b>{trading_style}</b> on {asset_desc}\n"
            f"💰 Dropped: ${deposit:,.2f}\n"
            f"🎯 {multiplier}x GAIN → Bagged: ${profit:,.2f}\n"
            f"🔥 {reason}\n"
            f"📈 Your ${deposit:,.2f} turned into ${profit:,.2f} – {percentage_gain}% ROI!\n"
            f"Time: {ts}\n\n"
            f"🏆 Community Crushing It:\n{social_text}\n\n"
            f"Jump in at {WEBSITE_URL}! {tag}"
        ),
        (
            f"🔥 <b>{symbol} MONEY PRINTER</b> 💸\n"
            f"{trading_style} on {asset_desc} went NUTS!\n"
            f"💵 Started with: ${deposit:,.2f}\n"
            f"💰 Cashed out: ${profit:,.2f} ({multiplier}x!)\n"
            f"🚀 {reason}\n"
            f"📊 That’s a {percentage_gain}% gain – ${deposit:,.2f} to ${profit:,.2f}!\n"
            f"Time: {ts}\n\n"
            f"🏆 Squad’s Lit:\n{social_text}\n\n"
            f"Join the wave at {WEBSITE_URL}! {tag}"
        ),
        (
            f"💥 <b>{symbol} BAG SECURED</b> 🚀\n"
            f"{trading_style} on {asset_desc} hit DIFFERENT!\n"
            f"💸 In: ${deposit:,.2f}\n"
            f"🤑 Out: ${profit:,.2f} ({multiplier}x gain!)\n"
            f"🔥 {reason}\n"
            f"📈 Flipped ${deposit:,.2f} into ${profit:,.2f} – {percentage_gain}% ROI!\n"
            f"Time: {ts}\n\n"
            f"🏆 Flex Kings:\n{social_text}\n\n"
            f"Get in at {WEBSITE_URL}! {tag}"
        ),
        (
            f"🌙 <b>{symbol} MOON SHOT</b> 🚀\n"
            f"{trading_style} on {asset_desc} was INSANE!\n"
            f"💰 Bet: ${deposit:,.2f}\n"
            f"💸 Won: ${profit:,.2f} ({multiplier}x!)\n"
            f"🔥 {reason}\n"
            f"📊 Your ${deposit:,.2f} became ${profit:,.2f} – {percentage_gain}% gain!\n"
            f"Time: {ts}\n\n"
            f"🏆 Crew’s Stacking:\n{social_text}\n\n"
            f"Join the vibe at {WEBSITE_URL}! {tag}"
        ),
        (
            f"💰 <b>{symbol} CASH GRAB</b> 💸\n"
            f"{trading_style} on {asset_desc} went WILD!\n"
            f"💵 Threw in: ${deposit:,.2f}\n"
            f"🤑 Pulled out: ${profit:,.2f} ({multiplier}x!)\n"
            f"🚀 {reason}\n"
            f"📈 Turned ${deposit:,.2f} into ${profit:,.2f} – {percentage_gain}% profit!\n"
            f"Time: {ts}\n\n"
            f"🏆 Gang’s Winning:\n{social_text}\n\n"
            f"Hop on at {WEBSITE_URL}! {tag}"
        ),
    ]
    return random.choice(templates)

# Craft a chart for the symbol (simulated pump)
def craft_price_chart(symbol):
    try:
        base_price = random.uniform(0.0005, 0.002) if symbol == "NIKY" else random.uniform(100, 1000)
        price_increase = random.randint(100, 1400 if symbol == "NIKY" else 700) / 100  # Higher for NIKY
        prices = [base_price * (1 + (price_increase * i / 50)) for i in range(51)]  # Linear pump
        labels = [f"T-{50-i}h" for i in range(50, -1, -1)]
        color = "#FFD700" if symbol == "NIKY" else "#00C4B4"
        bg_color = "rgba(255, 215, 0, 0.2)" if symbol == "NIKY" else "rgba(0, 196, 180, 0.2)"
        return {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": f"{symbol} Pump",
                    "data": prices,
                    "borderColor": color,
                    "backgroundColor": bg_color,
                    "fill": True
                }]
            },
            "options": {
                "responsive": True,
                "scales": {
                    "x": {"title": {"display": True, "text": "Time (Hours Ago)"}},
                    "y": {"title": {"display": True, "text": "Value"}}
                }
            }
        }
    except Exception as e:
        logger.error(f"Error creating chart for {symbol}: {e}")
        return None

# Log post content to DB
def log_post(symbol, content, deposit, profit):
    try:
        with engine.begin() as conn:
            conn.execute(
                "INSERT INTO posts (symbol, content, deposit, profit, posted_at) VALUES (:s, :c, :d, :pr, :t)",
                {"s": symbol, "c": content, "d": deposit, "pr": profit, "t": datetime.now(timezone.utc)}
            )
    except Exception as e:
        logger.error(f"Error logging post: {e}")

# Background posting loop for profit flex
async def flex_posting_loop(app):
    logger.info("Profit flex posting task started.")
    while True:
        try:
            wait_minutes = random.choice([20, 40])
            wait_seconds = wait_minutes * 60
            logger.info(f"Next flex post in {wait_minutes}m")
            await asyncio.sleep(wait_seconds)

            symbol = random.choices(ALL_SYMBOLS, weights=[30]*len(STOCK_SYMBOLS) + [20]*len(CRYPTO_SYMBOLS) + [30])[0]  # Higher weight for NIKY
            deposit, profit, percentage_gain, reason, trading_style = generate_flex_scenario(symbol)
            msg = craft_flex_message(symbol, deposit, profit, percentage_gain, reason, trading_style)
            try:
                await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode=constants.ParseMode.HTML)
                logger.info(f"[FLEX POSTED] {symbol} {trading_style} Deposit ${deposit:.2f} → Profit ${profit:.2f} ({percentage_gain}% gain)")
                log_post(symbol, msg, deposit, profit)
                
                chart = craft_price_chart(symbol)
                if chart:
                    await app.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=f"📈 {symbol} Pump Chart – Flex Mode On! 🚀",
                        parse_mode=constants.ParseMode.HTML
                    )
                    await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"```chartjs\n{chart}\n```")
            except Exception as e:
                logger.error(f"Failed to post flex for {symbol}: {e}")
            await asyncio.sleep(RATE_LIMIT_SECONDS)

            # Post community insights
            if random.random() < 0.2:
                user_df = fetch_user_stats()
                social_intro = random.choice([
                    "🏆 Community’s on FIRE:\n",
                    "🔥 Top traders killing it:\n",
                    "💪 Squad’s stacking WINS:\n",
                    "💸 Flex kings going hard:\n",
                    "🌟 Crew’s making BANK:\n",
                ])
                social_msg = social_intro
                if not user_df.empty:
                    for _, r in user_df.iterrows():
                        social_msg += f"{r['username']} — {r['wins']}/{r['total_trades']} trades • {r['win_rate']}% win rate\n"
                else:
                    for _ in range(4):
                        social_msg += f"Trader_{random.randint(1000,9999)} — {random.randint(10,50)} trades • {round(random.uniform(60,95),1)}% success\n"
                social_msg += f"\nJoin our flexes at {WEBSITE_URL}! #TradingSuccess"
                try:
                    await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=social_msg, parse_mode=constants.ParseMode.HTML)
                    logger.info("Posted community insights.")
                    log_post(None, social_msg, None, None)
                except Exception as e:
                    logger.error(f"Failed community post: {e}")

        except asyncio.CancelledError:
            logger.info("Flex posting loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in flex loop: {e}")
            await asyncio.sleep(5)

# /start handler
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    is_private = update.effective_chat.type == "private"
    user = update.effective_user
    if is_private:
        name = user.first_name or user.username or "there"
        text = random.choice([
            (
                f"Yo {name}! 👋 Ready to FLEX? 🤑\n"
                f"Insane gains on stocks (scalping vibes), crypto (HODL crushes), and $NIKY (meme pumps) 🚀\n"
                f"Scalping for stocks, Swing/DCA for crypto, Sniping for memes – we’re stacking BAGS! 💎🐾\n\n"
                f"Website: {WEBSITE_URL}\n\n"
                f"Use /flex <symbol> for a quick flex or /status for the scoop."
            ),
            (
                f"Hey {name}! 💪 Join the PROFIT PARTY! 🎉\n"
                f"Stocks (day trading fire), crypto (HODL wins), and $NIKY (meme coin madness) 🚀\n"
                f"From scalping to sniping, we’re making BANK! 💸🐾\n\n"
                f"Website: {WEBSITE_URL}\n\n"
                f"Drop /flex <symbol> for an instant flex or /status for deets."
            ),
            (
                f"What’s good, {name}? 🤑 Time to stack WINS!\n"
                f"Stocks (swing trade heat), crypto (DCA bangers), and $NIKY (pump riding) 🚀\n"
                f"Scalping, HODLing, sniping – we’re flexing HARD! 💎💸\n\n"
                f"Website: {WEBSITE_URL}\n\n"
                f"Hit /flex <symbol> for a flex or /status for the vibe."
            ),
        ])
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=constants.ParseMode.HTML)
        try:
            with engine.begin() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, display_name, wins, total_trades) VALUES (:id, :u, :d, 0, 0)",
                    {"id": str(user.id), "u": user.username or "unknown", "d": user.first_name or "Trader"}
                )
        except Exception as e:
            logger.error(f"Error adding user {user.id}: {e}")
    else:
        await context.bot.send_message(chat_id=chat_id, text="Profit flexes for stocks, crypto, and $NIKY incoming! 💎🚀", parse_mode=constants.ParseMode.HTML)

# /status handler
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = random.choice([
        (
            f"🔥 Bot’s FLEXING HARD:\n"
            f"Stocks (Scalping/Day/Swing): {', '.join(STOCK_SYMBOLS)}\n"
            f"Crypto (HODL/Swing/DCA): {', '.join(CRYPTO_SYMBOLS)}\n"
            f"Meme Coin (Sniping/Pump Riding): $NIKY (Onyx Dachshund on Solana)\n"
            f"Flex Posts: Every 20/40 mins – Gains up to 1400%! Join at {WEBSITE_URL}!"
        ),
        (
            f"💸 Bot’s stacking BAGS:\n"
            f"Stocks (Scalping & more): {', '.join(STOCK_SYMBOLS)}\n"
            f"Crypto (HODL & DCA): {', '.join(CRYPTO_SYMBOLS)}\n"
            f"$NIKY (Meme coin flips): Onyx Dachshund on Solana\n"
            f"Flexes drop every 20/40 mins – Up to 1400% gains! Hop in at {WEBSITE_URL}!"
        ),
        (
            f"🚀 Bot’s going CRAZY:\n"
            f"Stocks (Day Trading & Swing): {', '.join(STOCK_SYMBOLS)}\n"
            f"Crypto (Swing & Arbitrage): {', '.join(CRYPTO_SYMBOLS)}\n"
            f"$NIKY (Community Flips): Onyx Dachshund on Solana\n"
            f"Flexes every 20/40 mins – Stack gains up to 1400%! Join at {WEBSITE_URL}!"
        ),
    ])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode=constants.ParseMode.HTML)

# /help handler
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = random.choice([
        (
            f"Bot commands:\n"
            f"/start - Kick it off with a vibe & website link (private chat)\n"
            f"/status - Check monitored symbols & flex styles\n"
            f"/flex <symbol> - Drop an instant profit flex\n"
            f"/help - See this menu\n\n"
            f"Flexes every 20/40 mins – Stocks (scalping etc.), Crypto (HODL etc.), $NIKY (sniping etc.)! 💎🚀"
        ),
        (
            f"Commands to stack WINS:\n"
            f"/start - Get the vibe & website link (private chat)\n"
            f"/status - See what we’re flexing on\n"
            f"/flex <symbol> - Instant profit flex, let’s go!\n"
            f"/help - This list right here\n\n"
            f"Dropping flexes every 20/40 mins – Stocks, Crypto, $NIKY madness! 💸🚀"
        ),
    ])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode=constants.ParseMode.HTML)

# /flex handler
async def flex_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = (context.args[0] if context.args else "").upper()
    if symbol not in ALL_SYMBOLS:
        await update.message.reply_text(f"Symbol {symbol} not monitored. Use /status for available symbols.", parse_mode=constants.ParseMode.HTML)
        return
    
    deposit, profit, percentage_gain, reason, trading_style = generate_flex_scenario(symbol)
    msg = craft_flex_message(symbol, deposit, profit, percentage_gain, reason, trading_style)
    try:
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.HTML)
        logger.info(f"[ON-DEMAND FLEX] {symbol} {trading_style} Deposit ${deposit:.2f} → Profit ${profit:.2f}")
        log_post(symbol, msg, deposit, profit)
        
        chart = craft_price_chart(symbol)
        if chart:
            await update.message.reply_text(f"📈 {symbol} Pump Chart – Flex Mode On! 🚀", parse_mode=constants.ParseMode.HTML)
            await update.message.reply_text(f"```chartjs\n{chart}\n```")
    except Exception as e:
        logger.error(f"Failed to post on-demand flex for {symbol}: {e}")
        await update.message.reply_text("Error generating flex.", parse_mode=constants.ParseMode.HTML)

def main():
    if TELEGRAM_TOKEN is None:
        raise SystemExit("TELEGRAM_TOKEN not set in .env")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("flex", flex_handler))

    # Start background posting task
    async def on_startup(app):
        app.create_task(flex_posting_loop(app))
        logger.info("Flex posting task scheduled on startup.")

    app.post_init = on_startup

    logger.info("Bot starting. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
