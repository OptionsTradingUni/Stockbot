import asyncio
import random
import logging
from datetime import datetime, timezone, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants
from db import log_post, fetch_cached_rankings, announce_winner
from data import (
    ALL_SYMBOLS, WEBSITE_URL, TELEGRAM_CHAT_ID,
    RANKING_TRADERS, STOCK_SYMBOLS, CRYPTO_SYMBOLS, MEME_COINS
)
from profits import generate_profit_scenario, craft_profit_message
from rankings import craft_trade_status, craft_market_recap, craft_trending_ticker_alert

logger = logging.getLogger(__name__)

# -------------------------
# Profit Posting Loop
# -------------------------
async def profit_posting_loop(app):
    logger.info("Profit posting task started.")
    last_recap = datetime.now(timezone.utc) - timedelta(days=1)

    while True:
        try:
            # Posting intervals (weighted for realism)
            wait_minutes = random.choices(
                [5, 10, 15, 20, 30, 60, 120],
                weights=[0.3, 0.3, 0.25, 0.25, 0.1, 0.05, 0.02]
            )[0]
            logger.info(f"Next profit post in {wait_minutes} minutes")
            await asyncio.sleep(wait_minutes * 60)

            # Pick random asset
            symbol = random.choice(ALL_SYMBOLS)
            deposit, profit, percentage_gain, reason, trading_style, is_loss = generate_profit_scenario(symbol)
            trader_id, trader_name = random.choice(RANKING_TRADERS)

            # Build post
            msg, reply_markup, trader_id, trader_name = await craft_profit_message(
                symbol, deposit, profit, percentage_gain, reason, trading_style, is_loss
            )

            # Send to group
            await app.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode=constants.ParseMode.HTML,
                reply_markup=reply_markup
            )

            # Log in DB
            log_post(symbol, msg, deposit, profit, trader_id=trader_id)

            # Update rankings cache
            await fetch_cached_rankings(new_name=trader_name, new_profit=profit, app=app)

            # Big trade announcement
            if profit > 10000 and not is_loss:
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"🌟 Trade of the Day! 🌟\n{trader_name} made ${profit:,} on {symbol}!\nJoin {WEBSITE_URL}!",
                    parse_mode=constants.ParseMode.HTML
                )

            # Status update (20% chance)
            if random.random() < 0.2:
                status_msg, status_reply_markup = await craft_trade_status()
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=status_msg,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=status_reply_markup
                )

            # Daily recap once per day
            if (datetime.now(timezone.utc) - last_recap) >= timedelta(days=1):
                recap_msg, recap_reply_markup = craft_market_recap()
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=recap_msg,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=recap_reply_markup
                )
                last_recap = datetime.now(timezone.utc)

            # Trending ticker (10% chance)
            if random.random() < 0.1:
                trend_msg, trend_reply_markup = craft_trending_ticker_alert()
                if trend_msg:
                    await app.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=trend_msg,
                        parse_mode=constants.ParseMode.HTML,
                        reply_markup=trend_reply_markup
                    )

            # Random polls (5% chance)
            if random.random() < 0.05:
                poll_question = "Which asset pumps next?"
                options = random.sample(ALL_SYMBOLS, 4)
                await app.bot.send_poll(
                    chat_id=TELEGRAM_CHAT_ID,
                    question=poll_question,
                    options=options,
                    is_anonymous=False
                )

            # Winner announcements
            if random.random() < 0.05:
                await announce_winner("daily", app)
            if random.random() < 0.02:
                await announce_winner("weekly", app)
            if random.random() < 0.01:
                await announce_winner("monthly", app)

        except asyncio.CancelledError:
            logger.info("Profit posting loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in posting loop: {e}")
            await asyncio.sleep(5)
