import random
import json
from datetime import datetime, timezone, timedelta
import pandas as pd
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String,
    Float, DateTime, select, insert, update, delete
)
from dotenv import load_dotenv
import os
import logging

# Load environment
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///profit_flex.db")

# Logger
logger = logging.getLogger(__name__)

# Init DB
engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

# -------------------------
# TABLE DEFINITIONS
# -------------------------
rankings_cache = Table(
    "rankings_cache", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scope", String),  # overall, daily, weekly, monthly
    Column("content", String),  # JSON of rankings
    Column("timestamp", DateTime),
    extend_existing=True
)

posts = Table(
    "posts", metadata,
    Column("id", Integer, primary_key=True),
    Column("symbol", String),
    Column("content", String),
    Column("deposit", Float),
    Column("profit", Float),
    Column("posted_at", DateTime),
    Column("trader_id", String),
)

users = Table(
    "users", metadata,
    Column("user_id", String, primary_key=True),
    Column("username", String),
    Column("display_name", String),
    Column("wins", Integer),
    Column("total_trades", Integer),
    Column("total_profit", Float, default=0),
    Column("last_login", DateTime),
    Column("login_streak", Integer, default=0)
)

success_stories = Table(
    "success_stories", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_name", String, unique=True),
    Column("gender", String),
    Column("story", String),
    Column("image", String)
)

hall_of_fame = Table(
    "hall_of_fame", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_name", String),
    Column("profit", Float),
    Column("scope", String),  # daily, weekly, monthly
    Column("timestamp", DateTime)
)

trader_metadata = Table(
    "trader_metadata", metadata,
    Column("trader_id", String, primary_key=True),
    Column("country", String),
    Column("win_streak", Integer, default=0),
    Column("level", String, default="Rookie"),
    Column("total_deposit", Float, default=0.0),
    Column("total_profit", Float, default=0.0),
    Column("achievements", String)
)

trending_tickers = Table(
    "trending_tickers", metadata,
    Column("symbol", String, primary_key=True),
    Column("count", Integer, default=0),
    Column("last_posted", DateTime)
)

metadata.create_all(engine)

# db.py (add at bottom, after metadata.create_all(engine))

def get_success_stories():
    """
    Fetch success stories (name, story, image) from DB.
    Returns: {"male": [...], "female": [...]}
    """
    with engine.connect() as conn:
        rows = conn.execute(success_stories.select()).fetchall()
        stories = {"male": [], "female": []}
        for row in rows:
            stories[row.gender].append({
                "name": row.trader_name,
                "story": row.story,
                "image": row.image
            })
        return stories
# -------------------------
# IMPORT STATIC DATA
# -------------------------
from data import COUNTRY_TRADERS, RANKING_TRADERS, STOCK_SYMBOLS, CRYPTO_SYMBOLS, MEME_COINS

# -------------------------
# INITIALIZATION HELPERS
# -------------------------
def init_traders_if_needed():
    with engine.begin() as conn:
        existing = conn.execute(select(trader_metadata.c.trader_id)).fetchall()
        if existing:
            return
        logger.info("Initializing trader metadata...")
        for country, traders in COUNTRY_TRADERS.items():
            for trader_id, name in traders:
                conn.execute(insert(trader_metadata).values(
                    trader_id=trader_id,
                    country=country,
                    win_streak=0,
                    level="Rookie",
                    total_deposit=0.0,
                    total_profit=0.0,
                    achievements=""
                ))

def initialize_posts():
    with engine.begin() as conn:
        existing = conn.execute(select(posts)).fetchall()
        if existing:
            return
        for _ in range(200):
            symbol = random.choice(STOCK_SYMBOLS + CRYPTO_SYMBOLS + MEME_COINS)
            trader_id, _ = random.choice(RANKING_TRADERS)
            deposit = random.randint(100, 40000)
            profit = deposit * random.uniform(2, 8)
            posted_at = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
            conn.execute(insert(posts).values(
                symbol=symbol,
                content="Init post",
                deposit=deposit,
                profit=profit,
                posted_at=posted_at,
                trader_id=trader_id
            ))
            conn.execute(
                update(trader_metadata).where(trader_metadata.c.trader_id == trader_id).values(
                    total_profit=trader_metadata.c.total_profit + profit,
                    total_deposit=trader_metadata.c.total_deposit + deposit,
                )
            )

# -------------------------
# UTILITY FUNCTIONS
# -------------------------
def fetch_recent_profits():
    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                "SELECT profit FROM posts WHERE profit IS NOT NULL ORDER BY posted_at DESC LIMIT 50",
                conn
            )
            return set(df['profit'].tolist())
    except Exception as e:
        logger.error(f"Database error: {e}")
        return set()

def update_trader_level(trader_id, total_profit):
    level = "Rookie"
    if total_profit >= 100000:
        level = "Legend"
    elif total_profit >= 50000:
        level = "Whale"
    elif total_profit >= 10000:
        level = "Pro"
    with engine.begin() as conn:
        conn.execute(
            update(trader_metadata)
            .where(trader_metadata.c.trader_id == trader_id)
            .values(level=level)
        )

def assign_achievements(trader_id, profit, deposit, win_streak):
    achievements = []
    if profit / max(deposit, 1) > 20:
        achievements.append("Moonshot King")
    if deposit >= 20000:
        achievements.append("Whale")
    if win_streak >= 5:
        achievements.append("Streak Master")
    if profit >= 10000:
        achievements.append("Big Winner")
    if random.random() < 0.05:
        achievements.append("Diamond Hands")
    with engine.begin() as conn:
        existing = conn.execute(
            select(trader_metadata.c.achievements).where(trader_metadata.c.trader_id == trader_id)
        ).scalar() or ""
        current_achievements = set(existing.split(",")) if existing else set()
        current_achievements.update(achievements)
        conn.execute(
            update(trader_metadata)
            .where(trader_metadata.c.trader_id == trader_id)
            .values(achievements=",".join(current_achievements))
        )
    return achievements

# -------------------------
# RANKINGS + LEADERBOARDS
# -------------------------
def cache_rankings(scope, ranking_pairs):
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(delete(rankings_cache).where(rankings_cache.c.scope == scope))
        conn.execute(insert(rankings_cache).values(
            scope=scope,
            content=json.dumps(ranking_pairs),
            timestamp=now
        ))

def fetch_cached_rankings(scope="overall"):
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        row = conn.execute(select(rankings_cache).where(rankings_cache.c.scope == scope)).fetchone()
        if row:
            ts = row.timestamp
            if ts and (now - ts) < timedelta(hours=5):
                return json.loads(row.content)
        # fallback: rebuild
        return build_rankings_snapshot(scope)

def build_rankings_snapshot(scope="overall"):
    """scope = overall, daily, weekly, monthly"""
    with engine.connect() as conn:
        if scope == "daily":
            start = datetime.now(timezone.utc) - timedelta(days=1)
            df = pd.read_sql(
                "SELECT trader_id, SUM(profit) as total_profit FROM posts "
                "WHERE posted_at >= :start GROUP BY trader_id ORDER BY total_profit DESC",
                conn, params={"start": start}
            )
        elif scope == "weekly":
            start = datetime.now(timezone.utc) - timedelta(days=7)
            df = pd.read_sql(
                "SELECT trader_id, SUM(profit) as total_profit FROM posts "
                "WHERE posted_at >= :start GROUP BY trader_id ORDER BY total_profit DESC",
                conn, params={"start": start}
            )
        elif scope == "monthly":
            start = datetime.now(timezone.utc) - timedelta(days=30)
            df = pd.read_sql(
                "SELECT trader_id, SUM(profit) as total_profit FROM posts "
                "WHERE posted_at >= :start GROUP BY trader_id ORDER BY total_profit DESC",
                conn, params={"start": start}
            )
        else:
            df = pd.read_sql(
                "SELECT trader_id, total_profit FROM trader_metadata ORDER BY total_profit DESC",
                conn
            )
    ranking_pairs = []
    for row in df.itertuples():
        name = next((n for id, n in RANKING_TRADERS if id == row.trader_id), None)
        if name:
            ranking_pairs.append({"name": name, "profit": row.total_profit})
    ranking_pairs.sort(key=lambda x: x["profit"], reverse=True)
    ranking_pairs = ranking_pairs[:20]
    cache_rankings(scope, ranking_pairs)
    return ranking_pairs

def build_asset_leaderboard(asset_type):
    symbols = MEME_COINS if asset_type == "meme" else CRYPTO_SYMBOLS if asset_type == "crypto" else STOCK_SYMBOLS
    with engine.connect() as conn:
        df = pd.read_sql(
            f"SELECT trader_id, SUM(profit) as total_profit, SUM(deposit) as total_deposit FROM posts "
            f"WHERE symbol IN ({','.join([f'\"{s}\"' for s in symbols])}) "
            f"GROUP BY trader_id ORDER BY total_profit DESC LIMIT 10",
            conn
        )
    lines = []
    for i, row in enumerate(df.itertuples(), 1):
        name = next((n for id, n in RANKING_TRADERS if id == row.trader_id), None)
        if name:
            roi = round((row.total_profit / row.total_deposit) * 100, 1) if row.total_deposit > 0 else 0
            lines.append(f"{i}. {name} — ${int(row.total_profit):,} profit (ROI: {roi}%)")
    return lines

def build_country_leaderboard(country):
    with engine.connect() as conn:
        df = pd.read_sql(
            f"SELECT t.trader_id, t.total_profit FROM trader_metadata t "
            f"WHERE t.country = :c ORDER BY t.total_profit DESC LIMIT 10",
            conn, params={"c": country}
        )
    lines = []
    for i, row in enumerate(df.itertuples(), 1):
        name = next((n for id, n in RANKING_TRADERS if id == row.trader_id), None)
        if name:
            lines.append(f"{i}. {name} — ${int(row.total_profit):,} profit")
    return lines

def build_roi_leaderboard():
    with engine.connect() as conn:
        df = pd.read_sql(
            "SELECT trader_id, SUM(profit) as total_profit, SUM(deposit) as total_deposit FROM posts "
            "GROUP BY trader_id HAVING total_deposit > 0 ORDER BY (SUM(profit) / SUM(deposit)) DESC LIMIT 10",
            conn
        )
    lines = []
    for i, row in enumerate(df.itertuples(), 1):
        name = next((n for id, n in RANKING_TRADERS if id == row.trader_id), None)
        if name:
            roi = round((row.total_profit / row.total_deposit) * 100, 1)
            lines.append(f"{i}. {name} — {roi}% ROI (${int(row.total_profit):,} profit)")
    return lines

# -------------------------
# AUTO INITIALIZE
# -------------------------
init_traders_if_needed()
initialize_posts()
