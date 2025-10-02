import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from sqlalchemy import select
from database import engine, hall_of_fame

async def hall_of_fame_handler(update: Update, context, force_dm=False):
    with engine.connect() as conn:
        df = pd.read_sql(select(hall_of_fame.c.trader_name, hall_of_fame.c.profit, hall_of_fame.c.scope, hall_of_fame.c.timestamp).order_by(hall_of_fame.c.timestamp.desc()).limit(20), conn)
    if df.empty:
        txt = "No winners yet."
    else:
        rows = [f"🏆 <b>{r.trader_name}</b> — ${r.profit:,.0f} ({r.scope.capitalize()}, {r.timestamp:%Y-%m-%d})" for r in df.itertuples()]
        txt = "🏛️ <b>Hall of Fame</b>\n\n" + "\n".join(rows)

    uid = update.effective_user.id
    try:
        await context.bot.send_message(chat_id=uid, text=txt, parse_mode=constants.ParseMode.HTML,
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    except Exception:
        if not force_dm:
            await update.effective_message.reply_text("Open me in DM and press /start.")
