import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, text
from database import engine, trader_metadata, posts
from utils.cache import fetch_cached_rankings
from utils.formatting import top_list
from config import MEME_COINS, CRYPTO_SYMBOLS, STOCK_SYMBOLS

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]])

async def open_rankings_menu(bot, uid):
    lines, _ = await fetch_cached_rankings()
    msg = "🏆 <b>Top Traders</b>\n\n" + top_list(lines[:10])
    await bot.send_message(chat_id=uid, text=msg, parse_mode="HTML",
                           reply_markup=InlineKeyboardMarkup([
                               [InlineKeyboardButton("📈 ROI Leaderboard", callback_data="roi_leaderboard")],
                               [InlineKeyboardButton("⬅️ Back", callback_data="back")]
                           ]))

async def show_asset_leaderboard_menu(bot, uid):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Meme", callback_data="asset_meme")],
        [InlineKeyboardButton("₿ Crypto", callback_data="asset_crypto")],
        [InlineKeyboardButton("📊 Stocks", callback_data="asset_stocks")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ])
    await bot.send_message(chat_id=uid, text="Choose asset category:", reply_markup=kb)

def _asset_lines(asset_type):
    syms = MEME_COINS if asset_type=="meme" else CRYPTO_SYMBOLS if asset_type=="crypto" else STOCK_SYMBOLS
    with engine.connect() as conn:
        df = pd.read_sql(
            text(f"""
                SELECT trader_id, SUM(profit) as total_profit, SUM(deposit) as total_deposit
                FROM posts
                WHERE symbol IN ({",".join([f":s{i}" for i,_ in enumerate(syms)])})
                GROUP BY trader_id
                ORDER BY total_profit DESC
                LIMIT 10
            """),
            conn,
            params={f"s{i}": s for i,s in enumerate(syms)}
        )
    lines=[]
    if df.empty:
        return ["No trades in this category yet."]
    for i,row in enumerate(df.itertuples(),1):
        tm = engine.connect().execute(select(trader_metadata.c.name).where(trader_metadata.c.trader_id==row.trader_id)).scalar()
        roi = (row.total_profit/row.total_deposit*100) if row.total_deposit else 0
        mark = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        lines.append(f"{mark} {tm} — ${row.total_profit:,.0f} (ROI {roi:.1f}%)")
    return lines

async def show_asset_board(bot, uid, asset_type):
    lines = _asset_lines(asset_type)
    await bot.send_message(chat_id=uid, text=f"📈 <b>{asset_type.capitalize()} Leaderboard</b>\n\n"+"\n".join(lines),
                           parse_mode="HTML", reply_markup=back_kb())

async def show_country_menu(bot, uid):
    from data import COUNTRIES
    rows = []
    for c in COUNTRIES:
        rows.append([InlineKeyboardButton(c, callback_data=f"country_{c}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="back")])
    await bot.send_message(chat_id=uid, text="🌍 Choose a country:", reply_markup=InlineKeyboardMarkup(rows))

def _country_lines(country):
    with engine.connect() as conn:
        df = pd.read_sql(
            select(trader_metadata.c.name, trader_metadata.c.total_profit)
            .where(trader_metadata.c.country==country),
            conn
        )
    if df.empty:
        return [f"No traders from {country} yet."]
    df = df.sort_values("total_profit", ascending=False).head(10)
    lines=[]
    for i,row in enumerate(df.itertuples(),1):
        mark = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
        lines.append(f"{mark} {row.name} — ${row.total_profit:,.0f}")
    return lines

async def show_country_board(bot, uid, country):
    lines = _country_lines(country)
    await bot.send_message(chat_id=uid, text=f"🌍 <b>{country} Leaderboard</b>\n\n"+"\n".join(lines),
                           parse_mode="HTML", reply_markup=back_kb())

async def show_roi_board(bot, uid):
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT trader_id, SUM(profit) AS total_profit, SUM(deposit) AS total_deposit
                FROM posts
                GROUP BY trader_id
                HAVING total_deposit > 0
                ORDER BY (SUM(profit) / SUM(deposit)) DESC
                LIMIT 10
            """), conn)
    if df.empty:
        msg = "No trades recorded yet."
    else:
        rows=[]
        for i,row in enumerate(df.itertuples(),1):
            name = engine.connect().execute(select(trader_metadata.c.name).where(trader_metadata.c.trader_id==row.trader_id)).scalar()
            roi = row.total_profit/row.total_deposit*100 if row.total_deposit else 0
            mark = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
            rows.append(f"{mark} {name} — {roi:.1f}% ROI (${row.total_profit:,.0f} profit)")
        msg = "📈 <b>Top ROI</b>\n\n" + "\n".join(rows)
    await bot.send_message(chat_id=uid, text=msg, parse_mode="HTML", reply_markup=back_kb())
