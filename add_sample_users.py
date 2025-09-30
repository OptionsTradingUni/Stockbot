from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import random

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///profit_flex.db")
engine = create_engine(DATABASE_URL, echo=False)

sample_users = [
    {"user_id": "user_1", "username": "trader_jane", "display_name": "Jane Doe", "wins": 12, "total_trades": 20},
    {"user_id": "user_2", "username": "john_trades", "display_name": "John Smith", "wins": 7, "total_trades": 15},
    {"user_id": "user_3", "username": "alpha_trader", "display_name": "Alpha Trader", "wins": 3, "total_trades": 10},
    {"user_id": "user_4", "username": "market_guru", "display_name": "Market Guru", "wins": 25, "total_trades": 40}
]

try:
    with engine.begin() as conn:
        for user in sample_users:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username, display_name, wins, total_trades) VALUES (:id, :u, :d, :w, :t)",
                {"id": user["user_id"], "u": user["username"], "d": user["display_name"], "w": user["wins"], "t": user["total_trades"]}
            )
    print("Sample users added to database.")
except Exception as e:
    print(f"Error adding sample users: {e}")
