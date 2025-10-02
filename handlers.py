from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import CallbackContext
import sqlite3
from datetime import datetime
from db import get_top_traders, get_rankings_cache
from data import SUCCESS_STORY_TEMPLATES, TRADERS
import json
import random

async def start(update, context):
    try:
        user_id = update.effective_user.id
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("SELECT last_login, login_streak FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        streak = (user[1] or 0) + 1 if user else 1
        c.execute("INSERT OR REPLACE INTO users (user_id, username, last_login, login_streak) VALUES (?, ?, ?, ?)",
                  (user_id, update.effective_user.username or "Unknown", datetime.now(), streak))
        conn.commit()
        conn.close()

        text = f"Welcome to Options Trading University! 🎉\nLogin Streak: {streak} 🔥" if streak < 5 else f"🔥 Hot Streak Alert! {streak} logins in a row! 🏆"
        keyboard = [
            [InlineKeyboardButton("Rankings", callback_data="success_rankings")],
            [InlineKeyboardButton("Success Stories", callback_data="success_0")],
            [InlineKeyboardButton("Join Group", url="https://t.me/OptionsTradingUniversity")],
            [InlineKeyboardButton("Website", url="https://optionsuniversity.com")],
            [InlineKeyboardButton("Terms", url="https://optionsuniversity.com/terms")],
            [InlineKeyboardButton("Privacy", url="https://optionsuniversity.com/privacy")],
            [InlineKeyboardButton("Hall of Fame", callback_data="hall_of_fame")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.effective_chat.send_message(text, reply_markup=reply_markup)
    except Exception as e:
        await update.effective_message.reply_text("Error processing your request. Please try again.")
        context.bot.logger.error(f"Error in start: {e}")

async def status(update, context):
    try:
        mood = get_market_mood()
        text = f"📊 Market Overview\nMood: {mood}\n\nStocks: TSLA, AAPL, NVDA\nCrypto: BTC, ETH, SOL\nMeme Coins: NIKY, DOGE, PEPE\n\nUpdates every 5-20 mins!"
        keyboard = [
            [InlineKeyboardButton("View Rankings", callback_data="success_rankings")],
            [InlineKeyboardButton("Website", url="https://optionsuniversity.com")]
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text("Error fetching market status. Please try again.")
        context.bot.logger.error(f"Error in status: {e}")

async def trade_status(update, context):
    try:
        rankings = get_top_traders(15)
        text = f"🏆 Top Traders\n\n" + "\n".join([f"{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'{i+1}.'} {t['name']} ({t['nationality']}) - ${t['profit']:,} ({t['level']}{', ' + t['badges'] if t['badges'] else ''})" for i, t in enumerate(rankings[:5])])
        text += f"\n\nMarket Mood: {get_market_mood()}"
        keyboard = [
            [InlineKeyboardButton("Full Rankings", callback_data="success_rankings")]
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text("Error fetching trade status. Please try again.")
        context.bot.logger.error(f"Error in trade_status: {e}")

async def help_command(update, context):
    try:
        text = "📚 Commands:\n/start - Welcome & menu\n/status - Market overview\n/trade_status - Top traders\n/hall_of_fame - Past winners\n/help - This list"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text("Error displaying help. Please try again.")
        context.bot.logger.error(f"Error in help_command: {e}")

async def hall_of_fame(update, context):
    try:
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute("SELECT name, nationality, profit, scope, date FROM hall_of_fame ORDER BY date DESC LIMIT 10")
        winners = c.fetchall()
        conn.close()
        text = "🏆 Hall of Fame\n\n" + "\n".join([f"{w[0]} ({w[1]}) - ${w[2]:,} ({w[3].capitalize()}, {w[4].strftime('%Y-%m-%d')})" for w in winners])
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text("Error fetching hall of fame. Please try again.")
        context.bot.logger.error(f"Error in hall_of_fame: {e}")

async def success_stories(update, context):
    try:
        index = int(update.callback_query.data.split("_")[1]) if "_" in update.callback_query.data else 0
        template = SUCCESS_STORY_TEMPLATES[index % len(SUCCESS_STORY_TEMPLATES)]
        trader = random.choice(TRADERS)
        gender = "male" if random.random() < 0.5 else "female"
        deposit = random.randint(100, 5000)
        profit = random.randint(1000, 20000)
        symbol = random.choice([s["name"] for s in template["symbols"]])
        image_url = template["image_url"].format(id=index + 1)
        text = f"🌟 Success Story\n{trader['name']} ({trader['nationality']})\nInvested: ${deposit:,}\nProfit: ${profit:,}\nSymbol: {symbol}"
        keyboard = [
            [InlineKeyboardButton("Previous", callback_data=f"success_{max(0, index-1)}"),
             InlineKeyboardButton("Next", callback_data=f"success_{index+1}")],
            [InlineKeyboardButton("Back to Menu", callback_data="success_rankings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query.message.chat.type != "private":
            await update.callback_query.message.delete()
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=image_url,
                caption=text,
                reply_markup=reply_markup
            )
            await update.callback_query.answer("Success story sent to your private chat!")
        else:
            await update.callback_query.message.edit_media(
                media=InputMediaPhoto(image_url, caption=text),
                reply_markup=reply_markup
            )
            await update.callback_query.answer()
    except Exception as e:
        await update.callback_query.answer("Error displaying success story. Please try again.")
        context.bot.logger.error(f"Error in success_stories: {e}")

async def prev_success(update, context):
    await success_stories(update, context)

async def next_success(update, context):
    await success_stories(update, context)

async def reaction_callback(update, context):
    try:
        reaction = update.callback_query.data
        conn = sqlite3.connect("trading_bot.db")
        c = conn.cursor()
        c.execute(f"UPDATE posts SET {reaction} = {reaction} + 1 WHERE id = ?", (update.callback_query.message.message_id,))
        conn.commit()
        conn.close()
        await update.callback_query.answer(f"You reacted with {reaction.title()}!")
        # Update message with reaction counts
        c = conn.cursor()
        c.execute("SELECT fire, rocket, shock FROM posts WHERE id = ?", (update.callback_query.message.message_id,))
        counts = c.fetchone()
        conn.close()
        reaction_text = f"\n\n🔥 {counts[0]} 🚀 {counts[1]} 😱 {counts[2]}"
        await update.callback_query.message.edit_text(
            text=update.callback_query.message.text.split("\n\n🔥")[0] + reaction_text,
            reply_markup=update.callback_query.message.reply_markup
        )
    except Exception as e:
        await update.callback_query.answer("Error processing reaction. Please try again.")
        context.bot.logger.error(f"Error in reaction_callback: {e}")
