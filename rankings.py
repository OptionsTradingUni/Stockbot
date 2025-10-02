import json, random
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete, insert
from telegram import constants
from db import engine, trader_metadata, hall_of_fame
from data import RANKING_TRADERS, TELEGRAM_CHAT_ID

# --------------------------------
# Fetch Cached Rankings
# --------------------------------
async def fetch_cached_rankings(new_name=None, new_profit=None, app=None, scope="overall"):
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        row = conn.execute(select("id","content","timestamp").select_from("rankings_cache").where("id=1")).fetchone()
        refresh_needed = False
        ranking_pairs = []

        if row:
            ts = row.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ranking_pairs = json.loads(row.content)
            if (now - ts) >= timedelta(hours=5):
                refresh_needed = True

        if not row or refresh_needed:
            ranking_pairs = build_rankings_snapshot()
            conn.execute(delete("rankings_cache").where("id=1"))
            conn.execute(insert("rankings_cache").values(
                id=1,
                content=json.dumps(ranking_pairs),
                timestamp=now
            ))

        elif new_name and new_profit:
            ranking_pairs.append({"name": new_name, "profit": new_profit})
            ranking_pairs.sort(key=lambda x: x["profit"], reverse=True)
            ranking_pairs = ranking_pairs[:20]
            conn.execute(delete("rankings_cache").where("id=1"))
            conn.execute(insert("rankings_cache").values(
                id=1,
                content=json.dumps(ranking_pairs),
                timestamp=now
            ))

            if app:
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"🔥 BREAKING: {new_name} entered Top 20 with ${new_profit:,} profit!",
                    parse_mode=constants.ParseMode.HTML
                )

        medals = {1:"🥇",2:"🥈",3:"🥉"}
        lines = []
        for i, entry in enumerate(ranking_pairs, start=1):
            badge = medals.get(i, f"{i}.")
            lines.append(f"{badge} {entry['name']} — ${entry['profit']:,} profit")
        return lines

# --------------------------------
# Build Snapshots
# --------------------------------
def build_rankings_snapshot():
    pairs = []
    with engine.connect() as conn:
        rows = conn.execute(select(trader_metadata.c.trader_id, trader_metadata.c.total_profit)).fetchall()
        for trader_id, profit in rows:
            name = next((n for tid,n in RANKING_TRADERS if tid==trader_id), None)
            if name:
                pairs.append({"name":name,"profit":profit})
    pairs.sort(key=lambda x:x["profit"], reverse=True)
    return pairs[:20]

# ROI leaderboard
def build_roi_leaderboard():
    with engine.connect() as conn:
        rows = conn.execute(
            "SELECT trader_id, SUM(profit) as total_profit, SUM(deposit) as total_deposit "
            "FROM posts GROUP BY trader_id HAVING total_deposit>0 ORDER BY (SUM(profit)/SUM(deposit)) DESC LIMIT 10"
        ).fetchall()
    medals={1:"🥇",2:"🥈",3:"🥉"}
    lines=[]
    for i,row in enumerate(rows,1):
        name = next((n for tid,n in RANKING_TRADERS if tid==row.trader_id), None)
        if name:
            roi = round((row.total_profit/row.total_deposit)*100,1)
            badge=medals.get(i,f"{i}.")
            lines.append(f"{badge} {name} — {roi}% ROI (${row.total_profit:,})")
    return lines

# Country leaderboard
def build_country_leaderboard(country):
    with engine.connect() as conn:
        rows=conn.execute(
            f"SELECT trader_id,total_profit FROM trader_metadata WHERE country='{country}' ORDER BY total_profit DESC LIMIT 10"
        ).fetchall()
    medals={1:"🥇",2:"🥈",3:"🥉"}
    return [f"{medals.get(i,f'{i}.')} {next((n for tid,n in RANKING_TRADERS if tid==row.trader_id),None)} — ${int(row.total_profit):,}"
            for i,row in enumerate(rows,1)]

# Daily/Weekly/Monthly winners → hall of fame
async def announce_winner(scope, app):
    lines = await fetch_cached_rankings(scope=scope)
    if not lines: return
    winner_line = lines[0]
    winner_name = winner_line.split("—")[0].split()[-1]
    winner_profit = int("".join([c for c in winner_line.split("—")[1] if c.isdigit()]))
    with engine.begin() as conn:
        conn.execute(insert(hall_of_fame).values(
            trader_name=winner_name,profit=winner_profit,scope=scope,timestamp=datetime.now(timezone.utc)
        ))
    msg=f"🔥 {scope.capitalize()} Winner 🏆\n👑 {winner_name} made ${winner_profit:,}!"
    await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID,text=msg,parse_mode=constants.ParseMode.HTML)
