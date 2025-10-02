import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import engine, success_stories
from sqlalchemy import select, insert
from data import SUCCESS_TRADERS, SUCCESS_STORY_TEMPLATES

def _ensure_stories():
    with engine.begin() as conn:
        rows = conn.execute(select(success_stories)).fetchall()
        if rows:
            return
        # seed
        deposits=[300,400,500,600,700,800,1000,1200,1500,2000]*2
        random.shuffle(deposits)
        used=set()
        for gender, traders in SUCCESS_TRADERS.items():
            for _, name, image in traders:
                dep = deposits.pop()
                prof=None
                while prof is None or prof in used:
                    raw = dep*random.uniform(2,8)
                    prof=int(round(raw/50)*50)
                used.add(prof)
                tmpl = random.choice(SUCCESS_STORY_TEMPLATES[gender])
                text = tmpl.replace("${deposit}", f"${dep:,}").replace("${profit}", f"${prof:,}")
                conn.execute(insert(success_stories).values(trader_name=name, gender=gender, story=f"{name} {text}", image=image))

def _fetch(idx):
    with engine.connect() as conn:
        rows = conn.execute(select(success_stories.c.trader_name, success_stories.c.story, success_stories.c.image)).fetchall()
    if not rows:
        return None
    total=len(rows)
    idx=idx%total
    return idx, total, rows[idx]

async def show_story(bot, uid, idx=0):
    _ensure_stories()
    res=_fetch(idx)
    if not res: 
        await bot.send_message(chat_id=uid, text="No stories yet.")
        return
    idx,total,row=res
    text=f"📖 <b>Success Story</b>\n{row.story}"
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Prev", callback_data=f"story_prev_{idx}")],
        [InlineKeyboardButton("➡️ Next", callback_data=f"story_next_{idx}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ])
    await bot.send_photo(chat_id=uid, photo=row.image, caption=text, parse_mode="HTML", reply_markup=kb)

async def paginate_story(bot, uid, idx, forward=True):
    idx = idx+1 if forward else idx-1
    await show_story(bot, uid, idx)
