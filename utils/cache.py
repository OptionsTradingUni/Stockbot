import json
from datetime import datetime, timezone, timedelta
import pandas as pd
from sqlalchemy import select, insert, delete, update
from database import engine, rankings_cache, trader_metadata
from config import LEADERBOARD_TTL_HOURS

# Build rankings snapshot from trader_metadata (top 20)
def build_rankings_snapshot():
    with engine.connect() as conn:
        df = pd.read_sql(
            select(trader_metadata.c.name, trader_metadata.c.total_profit, trader_metadata.c.level, trader_metadata.c.country, trader_metadata.c.win_streak),
            conn
        )
    df = df.sort_values("total_profit", ascending=False).head(20)
    return df.to_dict(orient="records")

def save_cache(rows):
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(delete(rankings_cache).where(rankings_cache.c.id == 1))
        conn.execute(insert(rankings_cache).values(id=1, content=json.dumps(rows), timestamp=now, scope="overall"))

def load_cache():
    with engine.connect() as conn:
        row = conn.execute(select(rankings_cache).where(rankings_cache.c.id == 1)).fetchone()
    return row

async def fetch_cached_rankings(new_name=None, new_profit=None, app=None):
    row = load_cache()
    now = datetime.now(timezone.utc)
    refresh = True
    if row:
        ts = row.timestamp or now - timedelta(hours=10)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        refresh = (now - ts) >= timedelta(hours=LEADERBOARD_TTL_HOURS)

    if refresh or not row:
        rows = build_rankings_snapshot()
        save_cache(rows)
    else:
        rows = json.loads(row.content)

    # optional update with a new trader profit (kick-in)
    if new_name and new_profit:
        exists = False
        for r in rows:
            if r["name"] == new_name:
                r["total_profit"] = max(r["total_profit"], new_profit)
                exists = True
                break
        if not exists:
            rows.append({"name": new_name, "total_profit": new_profit, "level": "Rookie", "country": "Unknown", "win_streak": 0})
        rows = sorted(rows, key=lambda x: x["total_profit"], reverse=True)[:20]
        save_cache(rows)
        if app:
            await app.bot.send_message(chat_id=app.bot.id, text="")  # no-op; avoid spam to groups

    # Format lines ready for display
    lines = []
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for i, r in enumerate(rows):
        mark = medals.get(i, f"{i+1}.")
        nm = r["name"]
        val = r["total_profit"]
        lvl = r.get("level", "Rookie")
        ctry = r.get("country", "Unknown")
        ws = r.get("win_streak", 0)
        extra = f" | Streak {ws}" if ws >= 3 else ""
        lines.append(f"{mark} {nm} — ${val:,.0f} profit ({lvl}, {ctry}){extra}")

    return lines, rows
