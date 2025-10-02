import random
from datetime import datetime, timezone, timedelta
import pandas as pd
from sqlalchemy import select, insert, update
from database import engine, posts, trader_metadata, trending_tickers, hall_of_fame
from config import ALL_SYMBOLS, MEME_COINS, CRYPTO_SYMBOLS, STOCK_SYMBOLS, TELEGRAM_CHAT_ID, RATE_LIMIT_SECONDS, WEBSITE_URL
from utils.cache import fetch_cached_rankings
from utils.mood import market_mood

_used_profits = {}
_used_deposits = {}
DEP_TTL = 6 * 3600
PROF_TTL = 12 * 3600

NEWS = {
    "stocks": ["surged after strong earnings","climbed on analyst upgrade","rallied on new product","gained on partnership","spiked on sentiment"],
    "crypto": ["pumped after whale accumulation","rose on adoption news","surged on upgrade","gained on listing","spiked with DeFi"],
    "meme":   ["mooned after viral tweet","pumped on community hype","surged with influencer","rocketed after Reddit buzz","spiked on volume"]
}

def _prune(d, ttl):
    now = datetime.now().timestamp()
    for k,v in list(d.items()):
        if now - v > ttl:
            d.pop(k, None)

def _unique_deposit(a,b):
    _prune(_used_deposits, DEP_TTL)
    now = datetime.now().timestamp()
    for _ in range(200):
        x = random.randint(a,b)
        if x not in _used_deposits:
            _used_deposits[x]=now
            return x
    # fallback
    oldest = min(_used_deposits, key=_used_deposits.get)
    _used_deposits[oldest]=now
    return oldest

def _unique_profit(fn):
    _prune(_used_profits, PROF_TTL)
    now = datetime.now().timestamp()
    for _ in range(500):
        raw = fn()
        prof = int(raw//50*50)
        if prof not in _used_profits:
            _used_profits[prof]=now
            return prof
    # fallback
    if _used_profits:
        oldest = min(_used_profits, key=_used_profits.get)
        _used_profits[oldest]=now
        return oldest
    return int(fn()//50*50)

def generate_profit_scenario(symbol):
    is_loss = random.random() < 0.05
    if symbol in MEME_COINS:
        dep = _unique_deposit(500, 7000)
        if is_loss:
            profit = -random.randint(400, 1400)
        else:
            mult = random.uniform(5,50) if random.random()<0.9 else random.uniform(30,100)
            profit = _unique_profit(lambda: dep*mult)
    else:
        r=random.random()
        if r<0.35:
            dep=_unique_deposit(100,900); lo,hi=2.0,8.0
        elif r<0.85:
            dep=_unique_deposit(500,8500); lo,hi=2.0,8.0
        else:
            dep=_unique_deposit(20000,40000); lo,hi=2.0,5.0
        if is_loss:
            profit = -random.randint(400,1400)
        else:
            mult=random.uniform(lo,hi)
            profit=_unique_profit(lambda: dep*mult)

    pct_gain = round(((profit/dep)-1)*100,1) if profit>0 else round((profit/dep)*100,1)

    if symbol in MEME_COINS:
        cat="meme"
        style=random.choice(["Early Sniping","Pump Riding","Community Flip","Airdrop Hunt"])
    elif symbol in CRYPTO_SYMBOLS:
        cat="crypto"
        style=random.choice(["HODL","Swing","DCA","Arbitrage","Leverage"])
    else:
        cat="stocks"
        style=random.choice(["Scalping","Day Trade","Swing","Position"])

    catalyst = random.choice(NEWS[cat]) if profit>0 else "hit by sudden volatility"
    desc = f"{symbol} {style} {('lost' if profit<0 else 'gained')} ({catalyst})."
    return dep, profit, pct_gain, desc, style, (profit<0)

async def posting_loop(app):
    from utils.formatting import money
    from data import RANKING_TRADERS
    while True:
        try:
            wait_min = random.choices([5,10,15,20,30,60,120],[30,30,20,10,6,3,1])[0]
            await app.bot.send_chat_action(chat_id=TELEGRAM_CHAT_ID, action="typing")
            await asyncio.sleep(wait_min*60)

            symbol = random.choice(ALL_SYMBOLS)
            dep, prof, pct_gain, reason, style, is_loss = generate_profit_scenario(symbol)
            trader_id, trader_name = random.choice(RANKING_TRADERS)

            lines, _rows = await fetch_cached_rankings(new_name=trader_name, new_profit=max(prof,0), app=app)
            top5 = "\n".join(lines[:5])
            mood = market_mood()

            msg = (
                f"{'📉' if is_loss else '📈'} <b>{symbol} {'Loss' if is_loss else 'Profit'} Update</b>\n"
                f"{style}\n"
                f"💰 Invested: {money(dep)}\n"
                f"{'📉 Loss' if is_loss else '🎯 Realized'}: {money(abs(prof))} ({pct_gain:+.1f}%)\n"
                f"{'🚨' if is_loss else '🔥'} {reason}\n\n"
                f"🏆 Top Rankings (Live):\n{top5}\n\n"
                f"📊 Market mood: {mood}\n"
                f"Join us → {WEBSITE_URL}"
            )

            kb = [[
                {"text":"🏆 View Rankings","callback_data":"rankings"},
                {"text":"💸 Simulate Trade","callback_data":"simulate_trade"}
            ],[
                {"text":"🔥","callback_data":"react_fire"},
                {"text":"🚀","callback_data":"react_rocket"},
                {"text":"😱","callback_data":"react_shock"}
            ]]

            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(**b) for b in row] for row in kb])

            await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="HTML", reply_markup=reply_markup)

            # Log post & update trader metadata
            with engine.begin() as conn:
                conn.execute(insert(posts).values(
                    symbol=symbol, content=msg, deposit=dep, profit=prof,
                    posted_at=datetime.now(timezone.utc), trader_id=trader_id
                ))
                # update streak, totals
                if prof>0:
                    conn.execute(update(trader_metadata).where(trader_metadata.c.trader_id==trader_id).values(
                        total_profit=trader_metadata.c.total_profit+prof,
                        total_deposit=trader_metadata.c.total_deposit+dep,
                        win_streak=trader_metadata.c.win_streak+1
                    ))
                else:
                    conn.execute(update(trader_metadata).where(trader_metadata.c.trader_id==trader_id).values(
                        total_deposit=trader_metadata.c.total_deposit+dep,
                        win_streak=0
                    ))

            # occasional extras
            if random.random()<0.20:
                # post compact rankings card
                card = "🏆 Quick Board\n" + "\n".join(lines[:10])
                await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=card)

            # random daily/weekly/monthly winner announcements (light)
            if random.random()<0.05:
                await announce_winner("daily", app)
            if random.random()<0.02:
                await announce_winner("weekly", app)
            if random.random()<0.01:
                await announce_winner("monthly", app)

            await asyncio.sleep(RATE_LIMIT_SECONDS)
        except Exception as e:
            await asyncio.sleep(5)

async def announce_winner(scope, app):
    # Winner is top of cached ranking right now
    lines, rows = await fetch_cached_rankings()
    if not rows:
        return
    winner = rows[0]
    nm = winner["name"]
    total = winner["total_profit"]
    msg = f"👑 <b>{scope.capitalize()} Winner</b>\n{nm} — ${total:,.0f} profit\nAdded to Hall of Fame."
    await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="HTML")

    with engine.begin() as conn:
        conn.execute(insert(hall_of_fame).values(
            trader_name=nm, profit=total, scope=scope, timestamp=datetime.now(timezone.utc)
        ))
