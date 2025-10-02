import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, insert, update
from config import STOCK_SYMBOLS, CRYPTO_SYMBOLS, MEME_COINS, ALL_SYMBOLS, WEBSITE_URL
from db import engine, posts, trader_metadata, trending_tickers
from data import RANKING_TRADERS

# Uniqueness TTLs
used_deposits = {}
used_profits  = {}
DEPOSIT_TTL = 6 * 3600
PROFIT_TTL  = 12 * 3600

NEWS_CATALYSTS = {
    "stocks": [
        "strong earnings beat", "analyst upgrade", "partnership news",
        "product launch momentum", "macro tailwinds"
    ],
    "crypto": [
        "whale accumulation", "adoption headline", "protocol upgrade",
        "new listing", "DeFi catalyst"
    ],
    "meme": [
        "viral tweet", "community hype", "influencer nudge",
        "Reddit buzz", "meme volume spike"
    ],
}

def _prune(d, ttl):
    now = datetime.now().timestamp()
    for k, v in list(d.items()):
        if now - v > ttl:
            d.pop(k, None)

def _unique_deposit(lo, hi):
    _prune(used_deposits, DEPOSIT_TTL)
    now = datetime.now().timestamp()
    for _ in range(200):
        amt = random.randint(lo, hi)
        if amt not in used_deposits:
            used_deposits[amt] = now
            return amt
    # fallback reuse
    k = min(used_deposits, key=lambda x: used_deposits[x])
    used_deposits[k] = now
    return k

def _unique_profit(candidate_fn):
    _prune(used_profits, PROFIT_TTL)
    now = datetime.now().timestamp()
    for _ in range(400):
        raw = candidate_fn()
        val = int(raw // 50 * 50)
        if val not in used_profits:
            used_profits[val] = now
            return val
    k = min(used_profits, key=lambda x: used_profits[x]) if used_profits else int(candidate_fn() // 50 * 50)
    used_profits[k] = now
    return k

def generate_scenario(symbol):
    is_loss = random.random() < 0.05  # 5% flash crash
    # Deposits & multipliers
    if symbol in MEME_COINS:
        deposit = _unique_deposit(500, 7000)
        if is_loss:
            profit = -random.randint(500, 1200)
        else:
            mult = random.uniform(5, 50)
            if random.random() < 0.10:
                mult = random.uniform(30, 100)
            profit = _unique_profit(lambda: deposit * mult)
        cat = "meme"
    else:
        r = random.random()
        if r < 0.35:
            deposit = _unique_deposit(100, 900)
            mult_low, mult_high = 2.0, 8.0
        elif r < 0.85:
            deposit = _unique_deposit(500, 8500)
            mult_low, mult_high = 2.0, 8.0
        else:
            deposit = _unique_deposit(20000, 40000)  # whale
            mult_low, mult_high = 2.0, 5.0
        if is_loss:
            profit = -random.randint(500, 1200)
        else:
            profit = _unique_profit(lambda: deposit * random.uniform(mult_low, mult_high))
        cat = "crypto" if symbol in CRYPTO_SYMBOLS else "stocks"

    pct = round((profit / deposit - 1) * 100, 1) if not is_loss else round(profit / deposit * 100, 1)
    trading_style = {
        "stocks": ["Scalping", "Day Trading", "Swing Trade", "Position Trade"],
        "crypto": ["HODL", "Swing Trade", "DCA", "Arbitrage", "Leverage"],
        "meme": ["Early Sniping", "Pump Riding", "Community Flip", "Airdrop Hunt"],
    }[cat]
    style = random.choice(trading_style)
    catalyst = random.choice(NEWS_CATALYSTS["meme" if cat=="meme" else cat])
    reason = f"{symbol} {('dumped' if is_loss else 'ran')} after {catalyst} (+{abs(pct)}%{' loss' if is_loss else ''})"
    return deposit, profit, pct, reason, style, is_loss

def upsert_trending(symbol):
    with engine.begin() as conn:
        row = conn.execute(select(trending_tickers.c.count).where(trending_tickers.c.symbol == symbol)).fetchone()
        if row:
            conn.execute(update(trending_tickers).where(trending_tickers.c.symbol == symbol).values(
                count=row[0] + 1, last_posted=datetime.now(timezone.utc)
            ))
        else:
            conn.execute(insert(trending_tickers).values(
                symbol=symbol, count=1, last_posted=datetime.now(timezone.utc)
            ))

def log_trade(symbol, content, deposit, profit, trader_id):
    with engine.begin() as conn:
        conn.execute(insert(posts).values(
            symbol=symbol, content=content, deposit=deposit, profit=profit,
            posted_at=datetime.now(timezone.utc), trader_id=trader_id
        ))
        # update trader meta (streak/levels done in handlers to keep single place if you prefer)
        if profit > 0:
            conn.execute(update(trader_metadata).where(trader_metadata.c.trader_id == trader_id).values(
                total_profit=trader_metadata.c.total_profit + profit,
                total_deposit=trader_metadata.c.total_deposit + deposit,
                win_streak=trader_metadata.c.win_streak + 1
            ))
        else:
            conn.execute(update(trader_metadata).where(trader_metadata.c.trader_id == trader_id).values(
                win_streak=0
            ))
