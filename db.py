import sqlite3
import random
from datetime import datetime, timedelta
import logging
from data import TRADERS, SUCCESS_STORY_TEMPLATES

logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect("trading_bot.db")
    c = conn.cursor()

    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        timestamp DATETIME,
        fire INTEGER DEFAULT 0,
        rocket INTEGER DEFAULT 0,
        shock INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        last_login DATETIME,
        login_streak INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS success_stories (
        id INTEGER PRIMARY KEY,
        name TEXT,
        nationality TEXT,
        gender TEXT,
        deposit INTEGER,
        profit INTEGER,
        symbol TEXT,
        image_url TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS hall_of_fame (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        nationality TEXT,
        profit INTEGER,
        scope TEXT,
        date DATETIME
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS trader_metadata (
        trader_id INTEGER PRIMARY KEY,
        name TEXT,
        nationality TEXT,
        profit INTEGER,
        roi REAL,
        level TEXT,
        badges TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS trending_tickers (
        symbol TEXT PRIMARY KEY,
        count INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS rankings_cache (
        type TEXT PRIMARY KEY,
        data TEXT,
        timestamp DATETIME
    )''')

    # Check schema version
    c.execute("SELECT value FROM config WHERE key = 'version'")
    current_version = c.fetchone()
    new_version = "1.0.0"
    if not current_version or current_version[0] != new_version:
        logger.info("Initializing database with new version")
        c.execute("DELETE FROM posts")
        c.execute("DELETE FROM trader_metadata")
        c.execute("DELETE FROM hall_of_fame")
        c.execute("DELETE FROM success_stories")
        c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('version', ?)", (new_version,))

        # Initialize trader_metadata
        for trader in TRADERS:
            profit = random.randint(1000, 50000)
            roi = round(random.uniform(5.0, 300.0), 2)
            level = "Rookie" if profit < 5000 else "Pro" if profit < 20000 else "Whale" if profit < 40000 else "Legend"
            badges = random.choice(["", "Moonshot King", "Streak Master", "Meme Lord"]) if profit > 10000 else ""
            c.execute("INSERT INTO trader_metadata (trader_id, name, nationality, profit, roi, level, badges) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (trader["id"], trader["name"], trader["nationality"], profit, roi, level, badges))

        # Initialize success_stories
        for i, template in enumerate(SUCCESS_STORY_TEMPLATES, 1):
            trader = random.choice(TRADERS)
            gender = "male" if random.random() < 0.5 else "female"
            deposit = random.randint(100, 5000)
            profit = random.randint(1000, 20000)
            symbol = random.choice([s["name"] for s in template["symbols"]])
            image_url = template["image_url"].format(id=i)
            c.execute("INSERT INTO success_stories (id, name, nationality, gender, deposit, profit, symbol, image_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (i, trader["name"], trader["nationality"], gender, deposit, profit, symbol, image_url))

        # Initialize hall of fame
        for i in range(50):
            trader = random.choice(TRADERS)
            profit = random.randint(5000, 100000)
            scope = random.choice(["daily", "weekly", "monthly"])
            date = datetime.now() - timedelta(days=random.randint(1, 365))
            c.execute("INSERT INTO hall_of_fame (name, nationality, profit, scope, date) VALUES (?, ?, ?, ?, ?)",
                      (trader["name"], trader["nationality"], profit, scope, date))

        conn.commit()
    conn.close()

def update_trader_profit(trader_id, profit, roi):
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("UPDATE trader_metadata SET profit = profit + ?, roi = ? WHERE trader_id = ?", (profit, roi, trader_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating trader profit: {e}")
    finally:
        conn.close()

def get_top_traders(limit=15, type="overall"):
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        if type == "overall":
            c.execute("SELECT name, nationality, profit, level, badges FROM trader_metadata ORDER BY profit DESC LIMIT ?", (limit,))
        elif type in ["stocks", "crypto", "meme"]:
            c.execute("SELECT t.name, t.nationality, t.profit, t.level, t.badges FROM trader_metadata t JOIN success_stories s ON t.name = s.name WHERE s.symbol IN (SELECT symbol FROM success_stories WHERE symbol LIKE ? GROUP BY symbol ORDER BY SUM(profit) DESC) ORDER BY t.profit DESC LIMIT 10", (f"{type}%",))
        elif type == "roi":
            c.execute("SELECT name, nationality, profit, level, badges, roi FROM trader_metadata ORDER BY roi DESC LIMIT 10")
        else:  # country
            c.execute("SELECT name, nationality, profit, level, badges FROM trader_metadata WHERE nationality = ? ORDER BY profit DESC LIMIT 10", (type,))
        traders = [{"name": row[0], "nationality": row[1], "profit": row[2], "level": row[3], "badges": row[4], "roi": row[5] if type == "roi" else None} for row in c.fetchall()]
        conn.close()
        return traders
    except Exception as e:
        logger.error(f"Error fetching top traders: {e}")
        return []

def get_rankings_cache(type):
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("SELECT data, timestamp FROM rankings_cache WHERE type = ?", (type,))
        result = c.fetchone()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error fetching rankings cache: {e}")
        return None

def update_rankings_cache(type, data):
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO rankings_cache (type, data, timestamp) VALUES (?, ?, ?)", (type, data, datetime.now()))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating rankings cache: {e}")
    finally:
        conn.close()

def update_trending_ticker(symbol):
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO trending_tickers (symbol, count) VALUES (?, COALESCE((SELECT count + 1 FROM trending_tickers WHERE symbol = ?), 1))", (symbol, symbol))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating trending ticker: {e}")
    finally:
        conn.close()

def get_trending_tickers():
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("SELECT symbol, count FROM trending_tickers WHERE count >= 3 ORDER BY count DESC LIMIT 4")
        tickers = c.fetchall()
        conn.close()
        return tickers
    except Exception as e:
        logger.error(f"Error fetching trending tickers: {e}")
        return []
