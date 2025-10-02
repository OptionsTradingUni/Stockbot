from telegram import Update
from telegram.ext import ContextTypes
from handlers.rankings import open_rankings_menu, show_asset_leaderboard_menu, show_country_menu, show_roi_board, show_asset_board, show_country_board
from handlers.stories import show_story, paginate_story
from handlers.hof import hall_of_fame_handler
from handlers.status import status_handler
from handlers.help import help_handler
from handlers.start import start_handler

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id

    async def dm(text=None, **kwargs):
        if text:
            return await context.bot.send_message(chat_id=uid, text=text, **kwargs)

    if data == "rankings":
        await open_rankings_menu(context.bot, uid)
    elif data == "asset_leaderboard":
        await show_asset_leaderboard_menu(context.bot, uid)
    elif data == "country_leaderboard":
        await show_country_menu(context.bot, uid)
    elif data.startswith("asset_"):          # asset_meme/asset_crypto/asset_stocks
        await show_asset_board(context.bot, uid, data.split("_")[1])
    elif data.startswith("country_"):        # country_Nigeria etc.
        await show_country_board(context.bot, uid, data.split("_",1)[1])
    elif data == "roi_leaderboard":
        await show_roi_board(context.bot, uid)
    elif data == "stories":
        await show_story(context.bot, uid, 0)
    elif data.startswith("story_next_") or data.startswith("story_prev_"):
        _, dir_, idx = data.split("_")
        await paginate_story(context.bot, uid, int(idx), dir_=="next")
    elif data == "hall_of_fame":
        await hall_of_fame_handler(update, context, force_dm=True)
    elif data == "simulate_trade":
        await status_handler(update, context, simulate=True)
    elif data in ("react_fire","react_rocket","react_shock"):
        await q.answer("Noted ✅")
    elif data == "back":
        await start_handler(update, context)
    elif data == "help":
        await help_handler(update, context, force_dm=True)
    else:
        await dm("Coming soon.")
