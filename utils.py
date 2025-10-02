import random
import json
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import sqlite3
from data import SYMBOLS, TRADERS
from db import update_trader_profit, get_top_traders, get_rankings_cache, update_rankings_cache, update_trending_ticker, get_trending_tickers

async def post_profit_alert(bot):
    try:
        # Randomize post interval
        intervals = [5, 10, 15, 20, 30, 60, 120]
        weights = [0.3, 0.3, 0.3, 0.3, 0.05, 0.02, 0.01]
        interval = random.choices(intervals, weights=weights, k=1)[0]

        # Select trader and symbol
        trader = random.choice(TRADERS)
        symbol = random.choices(
            [s for s in SYMBOLS if s["type"] == "meme"], k=1, weights=[0.7])[0] if random.random() < 0.7 else random.choice(SYMBOLS)
        deposit = random.randint(100, 5000)
        multiplier = random.uniform(1.1, 10.0)
        profit = int(deposit * (multiplier - 1))
        roi = round((multiplier - 1) * 100, 2)
        style = random.choice(["Scalping", "HODL", "Swing"])
        reason = random.choice(["Breakout pattern", "News catalyst", "Technical bounce", "Meme pump"])
        streak = random.randint(1, 10)

        # Update trader profit and trending ticker
        update_trader_profit(trader["id"], profit, roi)
        update_trending_ticker(symbol["name"])

        # Check rankings
        rankings = get_top_traders(15)
        rankings_text = "\n".join([f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'{i+1}.'} {t['name']} ({t['nationality']}) - ${t['profit']:,} ({t['level']}{', ' + t['badges'] if t['badges'] else ''})" for i, t in enumerate(rankings[:5])])
        cache = get_rankings_cache("overall")
        if cache and (datetime.now() - datetime.fromisoformat(cache[1])).total_seconds() < 5 * 3600:
            cached_rankings = json.loads(cache[0])
        else:
            update_rankings_cache("overall", json.dumps(rankings))
            cached_rankings = rankings

        # Check for leaderboard takeover
        if profit > cached_rankings[-1]["profit"]:
            update_rankings_cache("overall", json.dumps(rankings))
            await bot.send_message(
                chat_id="@OptionsTradingUniversity",
                text=f"🔥 Leaderboard Takeover! {trader['name']} storms into Top 15 with ${profit:,} profit! 🏆 #Leaderboard"
            )

        # Post types
        if profit > 10000 and random.random() < 0.1:
            message = f"🏆 Trade of the Day! {trader['name']} ({trader['nationality']}) crushed it with ${profit:,} on {symbol['name']}!\n💰 Invested: ${deposit:,}\n📈 ROI: {roi}%\n🎯 Style: {style}\n📰 Reason: {reason}\n🔥 Streak: {streak} trades\n\n🏆 Top 5 Traders:\n{rankings_text}\n\n#TradeOfTheDay"
        elif random.random() < 0.2:
            message = f"📊 Market Status Update\nMarket Mood: {get_market_mood()}\n\n🏆 Top 5 Traders:\n{rankings_text}\n\n#MarketUpdate"
        elif random.random() < 0.1:
            tickers = get_trending_tickers()
            if tickers:
                message = f"🔥 Trending Tickers Alert!\n" + "\n".join([f"{t[0]}: {t[1]} mentions" for t in tickers]) + "\n\n#Trending"
        elif random.random() < 0.05:
            poll_options = random.sample([s["name"] for s in SYMBOLS], 4)
            await bot.send_poll(
                chat_id="@OptionsTradingUniversity",
                question="Which asset will pump next? 📈",
                options=poll_options,
                is_anonymous=False
            )
            return
        else:
            message = f"🚨 {trader['name']} ({trader['nationality']}) just made ${profit:,} on {symbol['name']}!\n💰 Invested: ${deposit:,}\n📈 ROI: {roi}%\n🎯 Style: {style}\n📰 Reason: {reason}\n🔥 Streak: {streak} trades\n\n🏆 Top 5 Traders:\n{rankings_text}\n\n#TradingSuccess"

        # Send post
        keyboard = [
            [InlineKeyboardButton("🔥", callback_data="fire"), InlineKeyboardButton("🚀", callback_data="rocket"), InlineKeyboardButton("😱", callback_data="shock")],
            [InlineKeyboardButton("View Rankings", callback_data="success_rankings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        sent_message = await bot.send_message(
            chat_id="@OptionsTradingUniversity",
            text=message,
            reply_markup=reply_markup
        )

        # Add random reactions
        reactions = {
            "fire": random.randint(5, 80),
            "rocket": random.randint(5, 80),
            "shock": random.randint(5, 80)
        }
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("UPDATE posts SET fire = ?, rocket = ?, shock = ? WHERE id = ?",
                  (reactions["fire"], reactions["rocket"], reactions["shock"], sent_message.message_id))
        conn.commit()

        # Daily/weekly/monthly winners
        if random.random() < 0.05:
            winner = random.choice(rankings)
            scope = random.choice(["daily", "weekly", "monthly"])
            c.execute("INSERT INTO hall_of_fame (name, nationality, profit, scope, date) VALUES (?, ?, ?, ?, ?)",
                      (winner["name"], winner["nationality"], winner["profit"], scope, datetime.now()))
            conn.commit()
            await bot.send_message(
                chat_id="@OptionsTradingUniversity",
                text=f"🏆 {scope.capitalize()} Winner: {winner['name']} ({winner['nationality']}) with ${winner['profit']:,}! #HallOfFame"
            )
        conn.close()
    except Exception as e:
        logger.error(f"Error in post_profit_alert: {e}")

def initialize_data():
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM posts")
        if c.fetchone()[0] == 0:
            for _ in range(200):
                trader = random.choice(TRADERS)
                symbol = random.choice(SYMBOLS)
                profit = random.randint(1000, 50000)
                deposit = random.randint(100, 5000)
                roi = round(random.uniform(5.0, 300.0), 2)
                style = random.choice(["Scalping", "HODL", "Swing"])
                reason = random.choice(["Breakout pattern", "News catalyst", "Technical bounce", "Meme pump"])
                streak = random.randint(1, 10)
                message = f"🚨 {trader['name']} ({trader['nationality']}) made ${profit:,} on {symbol['name']}!\n💰 Invested: ${deposit:,}\n📈 ROI: {roi}%\n🎯 Style: {style}\n📰 Reason: {reason}\n🔥 Streak: {streak} trades"
                c.execute("INSERT INTO posts (message, timestamp, fire, rocket, shock) VALUES (?, ?, ?, ?, ?)",
                          (message, datetime.now() - timedelta(hours=random.randint(1, 720)), random.randint(5, 80), random.randint(5, 80), random.randint(5, 80)))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error initializing data: {e}")

def get_market_mood():
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("SELECT AVG(profit) FROM trader_metadata WHERE profit != 0 ORDER BY trader_id DESC LIMIT 10")
        avg_profit = c.fetchone()[0] or 0
        conn.close()
        if avg_profit > 5000:
            return "Bullish 🐂 (Greed: 61-100)"
        elif avg_profit < 0:
            return "Bearish 🐻 (Fear: 0-39)"
        return "Neutral 😐 (40-60)"
    except Exception as e:
        logger.error(f"Error getting market mood: {e}")
        return "Neutral 😐 (40-60)"
