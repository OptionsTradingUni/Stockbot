from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Text, Float
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///profit_flex.db")

engine = create_engine(DATABASE_URL, echo=False)
meta = MetaData()

posts = Table(
    "posts", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", String),
    Column("content", Text),
    Column("deposit", Float),
    Column("profit", Float),
    Column("posted_at", DateTime)
)

users = Table(
    "users", meta,
    Column("user_id", String, primary_key=True),
    Column("username", String),
    Column("display_name", String),
    Column("wins", Integer, default=0),
    Column("total_trades", Integer, default=0)
)

meta.create_all(engine)
print("Database and tables created/verified at:", DATABASE_URL)
