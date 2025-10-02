from sqlalchemy import select, text
import pandas as pd
from db import engine, posts, trader_metadata
from data import RANKING_TRADERS

def _name_from_id(tid):
    for _id, name in RANKING_TRADERS:
        if _id == tid: return name
    return None

def asset_leaderboard(symbols):
    q = text(f"""
        SELECT trader_id, SUM(profit) AS total_profit, SUM(deposit) AS total_deposit
        FROM posts
        WHERE symbol IN ({",".join([":s"+str(i) for i,_ in enumerate(symbols)])})
        GROUP BY trader_id ORDER BY total_profit DESC LIMIT 10
    """)
    params = {f"s{i}": s for i, s in enumerate(symbols)}
    df = pd.read_sql(q, engine, params=params)
    lines, medals = [], {1:"🥇",2:"🥈",3:"🥉"}
    for i, r in enumerate(df.itertuples(), 1):
        name = _name_from_id(r.trader_id)
        if not name: continue
        roi = round((r.total_profit / r.total_deposit) * 100, 1) if (r.total_deposit or 0) > 0 else 0
        lines.append(f"{medals.get(i, f'{i}.')} <b>{name}</b> — ${int(r.total_profit):,} profit (ROI: {roi}%)")
    return lines

def country_leaderboard(country):
    df = pd.read_sql(
        select(trader_metadata.c.trader_id, trader_metadata.c.total_profit)
        .where(trader_metadata.c.country == country)
        .order_by(trader_metadata.c.total_profit.desc()).limit(10),
        engine
    )
    lines, medals = [], {1:"🥇",2:"🥈",3:"🥉"}
    for i, r in enumerate(df.itertuples(), 1):
        name = _name_from_id(r.trader_id)
        if not name: continue
        lines.append(f"{medals.get(i, f'{i}.')} <b>{name}</b> — ${int(r.total_profit):,} profit")
    return lines

def roi_leaderboard():
    q = text("""
        SELECT trader_id, SUM(profit) AS total_profit, SUM(deposit) AS total_deposit
        FROM posts
        GROUP BY trader_id
        HAVING total_deposit > 0
        ORDER BY (SUM(profit) / SUM(deposit)) DESC
        LIMIT 10
    """)
    df = pd.read_sql(q, engine)
    lines, medals = [], {1:"🥇",2:"🥈",3:"🥉"}
    for i, r in enumerate(df.itertuples(), 1):
        name = _name_from_id(r.trader_id)
        if not name: continue
        roi = round((r.total_profit / r.total_deposit) * 100, 1)
        lines.append(f"{medals.get(i, f'{i}.')} <b>{name}</b> — {roi}% ROI (${int(r.total_profit):,})")
    return lines
