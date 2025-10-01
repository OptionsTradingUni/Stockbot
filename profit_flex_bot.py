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
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

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
SWING_TRADE_INTERVAL_MINUTES = int(os.getenv("SWING_TRADE_INTERVAL_MINUTES", "20"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///profit_flex.db")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://optionstradinguni.online/")
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "5"))

# Initialize DB engine and auto-create tables
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

metadata.create_all(engine)

# Telegram Bot instance
bot = Bot(token=TELEGRAM_TOKEN)

# Expanded Realistic Trader Names
REALISTIC_TRADER_NAMES = [
    ("JohnDoeTrader", "John Doe"),
    ("JaneSmithPro", "Jane Smith"),
    ("AlexJohnson", "Alex Johnson"),
    ("EmilyDavis", "Emily Davis"),
    ("MichaelBrown", "Michael Brown"),
    ("SarahWilson", "Sarah Wilson"),
    ("DavidMiller", "David Miller"),
    ("LauraTaylor", "Laura Taylor"),
    ("ChrisAnderson", "Chris Anderson"),
    ("AnnaMartinez", "Anna Martinez"),
    ("RobertGarcia", "Robert Garcia"),
    ("OliviaHernandez", "Olivia Hernandez"),
    ("JamesLopez", "James Lopez"),
    ("SophiaGonzalez", "Sophia Gonzalez"),
    ("WilliamRodriguez", "William Rodriguez"),
    ("MiaMartinez", "Mia Martinez"),
    ("DanielPerez", "Daniel Perez"),
    ("IsabellaSanchez", "Isabella Sanchez"),
    ("MatthewRamirez", "Matthew Ramirez"),
    ("CharlotteTorres", "Charlotte Torres"),
    ("EthanLee", "Ethan Lee"),
    ("AvaKing", "Ava King"),
    ("BenjaminScott", "Benjamin Scott"),
    ("GraceAdams", "Grace Adams"),
    ("LucasBaker", "Lucas Baker"),
    ("ChloeYoung", "Chloe Young"),
    ("HenryAllen", "Henry Allen"),
    ("EllaWright", "Ella Wright"),
    ("SamuelGreen", "Samuel Green"),
    ("VictoriaHarris", "Victoria Harris"),
]

# Helper: Fetch recent profits from DB
def fetch_recent_profits():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT profit FROM posts WHERE profit IS NOT NULL ORDER BY posted_at DESC LIMIT 50", conn)
            return set(df['profit'].tolist())
    except Exception as e:
        logger.error(f"Database error: {e}")
        return set()

# Helper: Generate profit scenario with realistic gains
def generate_profit_scenario(symbol):
    recent_profits = fetch_recent_profits()
    
    if symbol in MEME_COINS:
        deposit_options = [
            (309, 700),
            (700, random.choice([1200, 1500, 1800])),
            (1000, 2000),
            (1500, random.randint(3000, 6000)),
        ]
        max_attempts = 10
        for _ in range(max_attempts):
            deposit, target_profit = random.choice(deposit_options)
            if target_profit not in recent_profits:
                break
        else:
            deposit = 1500
            target_profit = random.randint(3000, 6000)
            while target_profit in recent_profits:
                target_profit = random.randint(3000, 6000)
    else:
        deposit_options = [
            (209, 300),
            (509, 800),
            (500, random.randint(600, 1000)),
            (1000, random.randint(1200, 2000)),
        ]
        max_attempts = 10
        for _ in range(max_attempts):
            deposit, target_profit = random.choice(deposit_options)
            if target_profit not in recent_profits:
                break
        else:
            deposit = 500
            target_profit = random.randint(600, 1000)
            while target_profit in recent_profits:
                target_profit = random.randint(600, 1000)
    
    multiplier = target_profit / deposit
    percentage_gain = round((multiplier - 1) * 100, 1)
    price_increase = int(percentage_gain * random.uniform(0.8, 1.2))
    
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
    
    return deposit, target_profit, percentage_gain, random.choice(reasons), trading_style

# Helper: Fetch user stats from DB for ranking
def fetch_user_stats():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT username, total_profit FROM users ORDER BY total_profit DESC LIMIT 10", conn)
            return df
    except Exception as e:
        logger.error(f"Database error: {e}")
        return pd.DataFrame()

# Craft a profit message with mentions
def craft_profit_message(symbol, deposit, profit, percentage_gain, reason, trading_style):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    multiplier = round(profit / deposit, 1)
    user_df = fetch_user_stats()
    social_lines = []
    for i, (_, r) in enumerate(user_df.iterrows(), 1):
        social_lines.append(f"{i}. {r['username']} — ${r['total_profit']:,.2f} profit")
    if user_df.empty:
        social_lines = [f"{i}. {random.choice(REALISTIC_TRADER_NAMES)[1]} — ${random.randint(1000,5000):,.2f} profit" for i in range(1, 11)]
    
    social_text = "\n".join(social_lines)
    mention = random.choice(REALISTIC_TRADER_NAMES)[1]  # Mention a random trader
    tag = "#MemeCoinGains #CryptoTrends" if symbol in MEME_COINS else "#StockMarket #CryptoWins"
    asset_desc = "Meme Coin" if symbol in MEME_COINS else symbol
    templates = [
        (
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
        ),
        (
            f"📊 <b>{symbol} Trade Success</b> 📊\n"
            f"{trading_style} on {asset_desc} paid off!\n"
            f"💵 Started with: ${deposit:,.2f}\n"
            f"💰 Secured: ${profit:,.2f} ({multiplier}x!)\n"
            f"🚀 {reason}\n"
            f"📈 {percentage_gain}% gain achieved!\n"
            f"Time: {ts}\n\n"
            f"🏆 Top Trader Rankings:\n{social_text}\n"
            f"👉 Kudos to {mention} for the winning strategy!\n\n"
            f"Discover more at Options Trading University! {tag}"
        ),
        (
            f"💥 <b>{symbol} Gain Alert</b> 💥\n"
            f"{trading_style} on {asset_desc} delivered!\n"
            f"💸 Invested: ${deposit:,.2f}\n"
            f"🤑 Realized: ${profit:,.2f} ({multiplier}x gain!)\n"
            f"🔥 {reason}\n"
            f"📈 Secured {percentage_gain}% ROI!\n"
            f"Time: {ts}\n\n"
            f"🏆 Top Trader Rankings:\n{social_text}\n"
            f"👉 Big props to {mention} for leading the charge!\n\n"
            f"Learn more at Options Trading University! {tag}"
        ),
    ]
    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings")],
        [InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return random.choice(templates), reply_markup

# Craft a success story
def craft_success_story():
    name = random.choice(REALISTIC_TRADER_NAMES)[1]
    profit = random.randint(2000, 10000)
    story_templates = [
        f"{name} turned $1,000 into ${profit} with a brilliant swing trade on AAPL, crediting OTU's expert guidance for their disciplined approach.",
        f"{name} grew $500 into ${profit} by mastering BTC HODL, thanks to OTU's market analysis that predicted a 150% surge.",
        f"{name} flipped $800 into ${profit} with NIKY pump riding, calling OTU's community support 'the secret to my success.'",
        f"{name} achieved ${profit} profit from ETH DCA, stating, 'OTU's step-by-step strategies transformed my trading career.'",
        f"{name} earned ${profit} through SOL arbitrage, praising OTU's real-time insights for navigating volatile markets.",
        f"{name} scaled $1,200 to ${profit} with TSLA scalping, attributing their win to OTU's proven techniques and mentorship.",
        f"{name} boosted $700 to ${profit} on DOGE with early sniping, thanks to OTU's timely alerts and community tips.",
        f"{name} turned $1,500 into ${profit} via SHIB community flips, crediting OTU's collaborative environment for their breakthrough.",
        f"{name} made ${profit} from NVDA position trading, saying, 'OTU's resources gave me the confidence to aim high.'",
        f"{name} grew $900 to ${profit} with GOOGL day trading, calling OTU 'the ultimate trading academy I needed.'",
        f"{name} generated ${profit} from META swing trades, 'OTU's expert mentorship was key to my consistent wins.'",
        f"{name} built $600 into ${profit} with SOL leverage trading, crediting OTU's risk management lessons.",
        f"{name} achieved ${profit} from AMZN scalping, 'OTU's community helped me spot the perfect entry points.'",
        f"{name} turned $1,200 into ${profit} with BTC arbitrage, 'OTU's strategies are gold for crypto traders.'",
        f"{name} earned ${profit} from NIKY airdrop hunts, 'OTU's alerts made all the difference.'",
    ]
    return random.choice(story_templates)

# Craft trade status message with success story
def craft_trade_status():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    user_df = fetch_user_stats()
    social_lines = []
    for i, (_, r) in enumerate(user_df.iterrows(), 1):
        social_lines.append(f"{i}. {r['username']} — ${r['total_profit']:,.2f} profit")
    if user_df.empty:
        social_lines = [f"{i}. {random.choice(REALISTIC_TRADER_NAMES)[1]} — ${random.randint(1000,5000):,.2f} profit" for i in range(1, 11)]
    
    social_text = "\n".join(social_lines)
    success_story = craft_success_story()
    return (
        f"🏆 <b>Top Trader Rankings</b> 🏆\n"
        f"As of {ts}:\n"
        f"{social_text}\n\n"
        f"📖 <b>Success Story</b>: {success_story}\n\n"
        f"Join the community at Options Trading University for more trading insights! #TradingCommunity"
    ), InlineKeyboardMarkup([[InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]]), success_story

# Log post content to DB and update user profits
def log_post(symbol, content, deposit, profit, user_id=None):
    try:
        with engine.begin() as conn:
            if user_id:
                conn.execute(
                    "UPDATE users SET total_profit = total_profit + :p WHERE user_id = :id",
                    {"p": profit, "id": user_id}
                )
            conn.execute(
                "INSERT INTO posts (symbol, content, deposit, profit, posted_at) VALUES (:s, :c, :d, :pr, :t)",
                {"s": symbol, "c": content, "d": deposit, "pr": profit, "t": datetime.now(timezone.utc)}
            )
    except Exception as e:
        logger.error(f"Database error: {e}")

# Background posting loop with mentions every 20 mins
async def profit_posting_loop(app):
    logger.info("Profit posting task started.")
    while True:
        try:
            wait_minutes = 20  # Fixed to 20 minutes for consistent mentions
            wait_seconds = wait_minutes * 60
            logger.info(f"Next profit post in {wait_minutes}m at {datetime.now(timezone.utc)}")
            await asyncio.sleep(wait_seconds)

            # Ensure meme coin posts every cycle
            symbol = random.choice(MEME_COINS)  # Prioritize meme coins
            if random.random() < 0.7:  # 70% chance for meme coin, 30% for others
                symbol = random.choice(MEME_COINS)
            else:
                symbol = random.choice([s for s in ALL_SYMBOLS if s not in MEME_COINS])
            
            deposit, profit, percentage_gain, reason, trading_style = generate_profit_scenario(symbol)
            msg, reply_markup = craft_profit_message(symbol, deposit, profit, percentage_gain, reason, trading_style)
            try:
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=msg,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=reply_markup
                )
                logger.info(f"[PROFIT POSTED] {symbol} {trading_style} Deposit ${deposit:.2f} → Profit ${profit:.2f}")
                log_post(symbol, msg, deposit, profit)
            except Exception as e:
                logger.error(f"Failed to post profit for {symbol}: {e}")
            await asyncio.sleep(RATE_LIMIT_SECONDS)

            if random.random() < 0.2:
                status_msg, status_reply_markup, success_story = craft_trade_status()
                try:
                    await app.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=status_msg,
                        parse_mode=constants.ParseMode.HTML,
                        reply_markup=status_reply_markup
                    )
                    logger.info("Posted trade status update.")
                    log_post(None, status_msg, None, None)
                except Exception as e:
                    logger.error(f"Failed to post trade status: {e}")

        except asyncio.CancelledError:
            logger.info("Profit posting loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in posting loop: {e}")
            await asyncio.sleep(5)

# /start handler
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    name = user.first_name or user.username or "Trader"
    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings")],
        [InlineKeyboardButton("Success Stories", callback_data="success")],
        [InlineKeyboardButton("Visit Website", url=WEBSITE_URL)],
        [InlineKeyboardButton("Terms of Service", callback_data="terms")],
        [InlineKeyboardButton("Privacy Policy", callback_data="privacy")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"Welcome, {name}!\n\n"
        f"At Options Trading University, we provide expert-led training, real-time market analysis, and a thriving community of successful traders. Our proven strategies have helped members achieve consistent gains, with profit updates shared every 20-40 minutes.\n"
        f"Why join us?\n"
        f"- Access to high-probability trades (up to 900% gains on meme coins).\n"
        f"- Guidance from top traders with a track record of success.\n"
        f"- Exclusive insights on stocks, crypto, and meme coins.\n\n"
        f"Start your journey to financial growth today!"
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=welcome_text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username, display_name, wins, total_trades, total_profit) "
                "VALUES (:id, :u, :d, 0, 0, 0)",
                {"id": str(user.id), "u": user.username or "unknown", "d": name}
            )
    except Exception as e:
        logger.error(f"Error adding user {user.id}: {e}")

# Callback handler for inline buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "rankings":
        status_msg, status_reply_markup = craft_trade_status()
        keyboard = [
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=status_msg,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=reply_markup
        )
    elif query.data == "success":
        success_story = craft_success_story()
        keyboard = [
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"📖 <b>Success Story</b>:\n{success_story}\n\nJoin Options Trading University to start your own journey!",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=reply_markup
        )
    elif query.data == "terms":
        terms_text = (
            f"📜 <b>Terms of Service</b> 📜\n\n"
            f"1. Acceptance of Terms: By using this bot, you agree to abide by these Terms of Service.\n"
            f"2. User Conduct: Users must comply with all applicable laws and not use the bot for illegal activities.\n"
            f"3. Disclaimer: All trading insights are for informational purposes only and not financial advice.\n"
            f"4. Limitation of Liability: Options Trading University is not liable for any losses incurred.\n"
            f"5. Changes to Terms: We may update these terms at any time. Continued use constitutes acceptance.\n\n"
            f"For full terms, visit our website."
        )
        keyboard = [
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=terms_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=reply_markup
        )
    elif query.data == "privacy":
        privacy_text = (
            f"🔒 <b>Privacy Policy</b> 🔒\n\n"
            f"1. Information Collected: We collect minimal data such as user IDs and usernames for bot functionality.\n"
            f"2. Use of Data: Data is used to personalize experiences and improve services.\n"
            f"3. Data Sharing: We do not sell your data. It may be shared with partners for service improvement.\n"
            f"4. Security: We use industry-standard measures to protect your data.\n"
            f"5. Changes to Policy: We may update this policy. Continued use constitutes acceptance.\n\n"
            f"For full privacy policy, visit our website."
        )
        keyboard = [
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=privacy_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=reply_markup
        )
    elif query.data == "back":
        # Back to main menu (e.g., start keyboard)
        keyboard = [
            [InlineKeyboardButton("View Rankings", callback_data="rankings")],
            [InlineKeyboardButton("Success Stories", callback_data="success")],
            [InlineKeyboardButton("Visit Website", url=WEBSITE_URL)],
            [InlineKeyboardButton("Terms of Service", callback_data="terms")],
            [InlineKeyboardButton("Privacy Policy", callback_data="privacy")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="Back to main menu.",
            reply_markup=reply_markup
        )

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
        [InlineKeyboardButton("View Rankings", callback_data="rankings")],
        [InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
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
        [InlineKeyboardButton("View Rankings", callback_data="rankings")],
        [InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )

# /trade_status handler
async def trade_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, reply_markup = craft_trade_status()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
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

    async def on_startup(app):
        app.create_task(profit_posting_loop(app))
        logger.info("Profit posting task scheduled on startup.")

    app.post_init = on_startup

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
