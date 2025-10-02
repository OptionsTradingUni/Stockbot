import random
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants
from db import fetch_recent_profits, assign_achievements
from data import (
    STOCK_SYMBOLS, CRYPTO_SYMBOLS, MEME_COINS, RANKING_TRADERS,
    WEBSITE_URL, NEWS_CATALYSTS, TELEGRAM_CHAT_ID
)

# -------------------------
# Generate Profit Scenarios
# -------------------------
def generate_profit_scenario(symbol):
    """
    Rules:
      - Meme coins: 5–50x normally; 10% chance 30–100x moonshot
        Deposits: 500–7000
      - Stocks/Crypto: 2–8x
        Deposits:
          • 35%: small tickets (100–900)
          • 50%: normal tickets (500–8500)
          • 15%: whale tickets (20k–40k)
      - 5% chance of loss (-500 to -1200)
    """
    is_loss = random.random() < 0.05  # 5% chance crash

    if symbol in MEME_COINS:
        deposit = random.randint(500, 7000)
        if is_loss:
            profit = -random.randint(500, 1200)
        else:
            mult = random.uniform(5, 50)
            if random.random() < 0.1:  # 10% moonshot
                mult = random.uniform(30, 100)
            profit = int(deposit * mult // 50 * 50)

    else:  # Stocks & Crypto
        r = random.random()
        if r < 0.35:
            deposit = random.randint(100, 900)
            mult_low, mult_high = 2, 8
        elif r < 0.85:
            deposit = random.randint(500, 8500)
            mult_low, mult_high = 2, 8
        else:
            deposit = random.randint(20000, 40000)
            mult_low, mult_high = 2, 5

        if is_loss:
            profit = -random.randint(500, 1200)
        else:
            profit = int(deposit * random.uniform(mult_low, mult_high) // 50 * 50)

    percentage_gain = round((profit / deposit - 1) * 100, 1) if not is_loss else round(profit / deposit * 100, 1)

    # -------------------------
    # Trading styles & reasons
    # -------------------------
    if symbol in STOCK_SYMBOLS:
        trading_style = random.choice(["Scalping", "Day Trading", "Swing Trade", "Position Trade"])
        reasons = [
            f"{symbol} {trading_style} {'crashed' if is_loss else 'climbed'} on momentum!",
            f"Solid {trading_style} execution on {symbol}.",
            f"{symbol} {'dipped' if is_loss else 'strength confirmed'} by clean {trading_style}.",
            f"Market {'punished' if is_loss else 'favored'} {symbol} with strong {trading_style}.",
        ]
    elif symbol in CRYPTO_SYMBOLS:
        trading_style = random.choice(["HODL", "Swing Trade", "DCA", "Arbitrage", "Leverage Trading"])
        reasons = [
            f"{symbol} {trading_style} {'collapsed' if is_loss else 'rode liquidity flows'}.",
            f"{trading_style} on {symbol} {'failed' if is_loss else 'aligned with breakout'}.",
            f"{symbol} {'sell-off' if is_loss else 'trend expansion'} with {trading_style}.",
        ]
    else:  # Meme coins
        trading_style = random.choice(["Early Sniping", "Pump Riding", "Community Flip", "Airdrop Hunt"])
        reasons = [
            f"{symbol} {'dumped hard' if is_loss else 'squeezed higher'} with {trading_style}.",
            f"Community {'panic sold' if is_loss else 'hype pushed'} {symbol} {'down' if is_loss else 'up'}.",
            f"{symbol} {'rug pulled' if is_loss else 'trend popped'} with chatter.",
        ]

    catalyst_type = "meme_coins" if symbol in MEME_COINS else "crypto" if symbol in CRYPTO_SYMBOLS else "stocks"
    news_catalyst = random.choice(NEWS_CATALYSTS[catalyst_type]) if not is_loss else "hit by sudden volatility!"
    reason = f"{random.choice(reasons)} ({news_catalyst})"

    return deposit, profit, percentage_gain, reason, trading_style, is_loss


# -------------------------
# Craft Profit Message
# -------------------------
async def craft_profit_message(symbol, deposit, profit, percentage_gain, reason, trading_style, is_loss, social_lines=None):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    multiplier = round(profit / deposit, 1) if not is_loss else round(profit / deposit, 2)

    mention = random.choice(RANKING_TRADERS)[1]
    tag = "#MemeCoinGains #CryptoTrends" if symbol in MEME_COINS else "#StockMarket #CryptoWins"
    asset_desc = "Meme Coin" if symbol in MEME_COINS else symbol

    trader_id, trader_name = random.choice(RANKING_TRADERS)

    msg = (
        f"{'📉' if is_loss else '📈'} {symbol} {'Loss' if is_loss else 'Profit'} Update\n"
        f"{trading_style} on {asset_desc}\n"
        f"💰 Invested: ${deposit:,.2f}\n"
        f"{'📉' if is_loss else '🎯'} {multiplier}x Return → {'Loss' if is_loss else 'Realized'}: ${abs(profit):,.2f}\n"
        f"{'🚨' if is_loss else '🔥'} {reason}\n"
        f"📊 {'Lost' if is_loss else 'Achieved'} {abs(percentage_gain)}% {'Loss' if is_loss else 'ROI'}!\n"
        f"Time: {ts}\n\n"
        f"👉 Shoutout to {mention} for inspiring us!\n"
        f"Join us at {WEBSITE_URL} {tag}"
    )

    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Visit Website", url=WEBSITE_URL)],
        [InlineKeyboardButton("🔥 React", callback_data="react_fire"),
         InlineKeyboardButton("🚀 React", callback_data="react_rocket"),
         InlineKeyboardButton("😱 React", callback_data="react_shock")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return msg, reply_markup, trader_id, trader_name
