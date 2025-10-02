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
from data import COUNTRY_TRADERS, RANKING_TRADERS, STOCK_SYMBOLS, CRYPTO_SYMBOLS, MEME_COINS

# Load environment
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///profit_flex.db")

# Logger
logger = logging.getLogger(__name__)

# Init DB
engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

# -------------------------
# TABLES
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

metadata.create_all(engine)

# -------------------------
# SUCCESS STORIES
# -------------------------
def get_success_stories():
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
# INIT HELPERS
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
        old_names = []
        if row:
            ts = row.timestamp
            if ts and (now - ts) < timedelta(hours=5):
                rankings = json.loads(row.content)
                old_names = [r["name"] for r in rankings]
                return rankings, None

        rankings = build_rankings_snapshot(scope)

        # detect new entry
        new_names = [r["name"] for r in rankings]
        new_entry = None
        if old_names:
            for name in new_names[:20]:
                if name not in old_names:
                    new_entry = name
                    break

        cache_rankings(scope, rankings)
        return rankings, new_entry

def build_rankings_snapshot(scope="overall"):
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
    return ranking_pairs[:20]

# -------------------------
# AUTO INIT
# -------------------------
init_traders_if_needed()
initialize_posts()
