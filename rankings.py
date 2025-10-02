import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete, insert, update
from db import engine, rankings_cache, trader_metadata
from data import RANKING_TRADERS
from config import RANKINGS_TTL_HOURS

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
# cache id = 1 always
CACHE_ID = 1

def _pairs_from_db():
    with engine.connect() as conn:
        rows = conn.execute(select(trader_metadata.c.trader_id, trader_metadata.c.total_profit)).fetchall()
    # map trader_id -> display name (only from RANKING_TRADERS)
    id_to_name = {tid: name for tid, name in RANKING_TRADERS}
    pairs = []
    for tid, total in rows:
        if tid in id_to_name:
            pairs.append({"trader_id": tid, "name": id_to_name[tid], "profit": int(total or 0)})
    pairs.sort(key=lambda x: x["profit"], reverse=True)
    return pairs[:20]

def get_cached_rankings(now=None):
    now = now or datetime.now(timezone.utc)
    with engine.begin() as conn:
        row = conn.execute(select(rankings_cache).where(rankings_cache.c.id == CACHE_ID)).fetchone()
        if row:
            ts = row.timestamp.replace(tzinfo=timezone.utc) if row.timestamp and row.timestamp.tzinfo is None else row.timestamp
            if ts and (now - ts) < timedelta(hours=RANKINGS_TTL_HOURS):
                return json.loads(row.content)
        # refresh
        pairs = _pairs_from_db()
        conn.execute(delete(rankings_cache).where(rankings_cache.c.id == CACHE_ID))
        conn.execute(insert(rankings_cache).values(id=CACHE_ID, content=json.dumps(pairs), timestamp=now))
        return pairs

def maybe_insert_and_refresh(new_name: str, new_profit: int):
    # Only insert if beats lowest of cached top-20
    pairs = get_cached_rankings()
    if not pairs:
        return get_cached_rankings()
    lowest = pairs[-1]["profit"]
    if new_profit <= lowest:
        return pairs
    # Replace or add (ensure name is from RANKING_TRADERS)
    id_by_name = {name: tid for tid, name in RANKING_TRADERS}
    if new_name not in id_by_name:
        return pairs
    tid = id_by_name[new_name]
    # merge & cap 20
    merged = [p for p in pairs if p["trader_id"] != tid] + [{"trader_id": tid, "name": new_name, "profit": new_profit}]
    merged.sort(key=lambda x: x["profit"], reverse=True)
    merged = merged[:20]
    # store
    with engine.begin() as conn:
        conn.execute(delete(rankings_cache).where(rankings_cache.c.id == CACHE_ID))
        conn.execute(insert(rankings_cache).values(id=CACHE_ID, content=json.dumps(merged), timestamp=datetime.now(timezone.utc)))
    return merged

def format_rank_lines(pairs):
    from sqlalchemy import select
    from db import trader_metadata, engine
    id_to_meta = {}
    with engine.connect() as conn:
        for p in pairs:
            row = conn.execute(select(trader_metadata.c.level, trader_metadata.c.win_streak, trader_metadata.c.country)
                               .where(trader_metadata.c.trader_id == p["trader_id"])).fetchone()
            id_to_meta[p["trader_id"]] = row or ("Rookie", 0, "Unknown")
    lines = []
    for i, p in enumerate(pairs, start=1):
        level, streak, country = id_to_meta.get(p["trader_id"], ("Rookie", 0, "Unknown"))
        medal = MEDALS.get(i, f"{i}.")
        lines.append(f"{medal} <b>{p['name']}</b> — ${p['profit']:,} profit ({level}, {country})")
    return lines
