# models.py

import os
from datetime import datetime
from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, 
                          String, Float, DateTime, text)
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("FATAL: DATABASE_URL is not set in .env")

engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

# All your table definitions now live here
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
    Column("wins", Integer, default=0),
    Column("total_trades", Integer, default=0),
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

rankings_cache = Table(
    "rankings_cache", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("content", String),
    Column("timestamp", DateTime)
)

trade_logs = Table(
    "trade_logs", metadata,
    Column("txid", String, primary_key=True),
    Column("timestamp", DateTime, default=datetime.utcnow),
    Column("symbol", String),
    Column("trader_name", String),
    Column("broker_name", String, default="Fidelity"),
    Column("direction", String, default="Buy/Sell"),
    Column("status", String, default="Filled"),
    Column("quantity", Float, default=1.0),
    Column("deposit", Float),
    Column("profit", Float),
    Column("roi", Float),  # Added
    Column("strategy", String),  # Added
    Column("reason", String),  # Added
    Column("posted_at", DateTime, default=datetime.utcnow),  # Added
    Column("entry_price", Float, nullable=True),
    Column("exit_price", Float, nullable=True),
    Column("total_value_exit", Float, nullable=True),
    Column("commission", Float, nullable=True),
    Column("slippage", Float, nullable=True)
)
# This command creates the tables if they don't exist
metadata.create_all(engine)
