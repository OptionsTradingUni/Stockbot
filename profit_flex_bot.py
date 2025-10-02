import os
import random
import asyncio
import logging
import json
from sqlalchemy import select, delete, insert, update, text, inspect
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ---- Uniqueness tracking (cooldowns) ----
used_deposits: dict[int, float] = {}  # value -> last_used_timestamp
used_profits: dict[int, float] = {}   # value -> last_used_timestamp

DEPOSIT_TTL_SECONDS = 6 * 60 * 60     # 6 hours
PROFIT_TTL_SECONDS = 12 * 60 * 60     # 12 hours

def _prune_used(used_dict: dict[int, float], ttl_seconds: int) -> None:
    """Remove entries older than ttl_seconds."""
    now = datetime.now().timestamp()
    stale = [v for v, ts in used_dict.items() if (now - ts) > ttl_seconds]
    for v in stale:
        used_dict.pop(v, None)

def _unique_deposit(min_val: int, max_val: int) -> int:
    """Return a deposit that hasn't been used recently."""
    _prune_used(used_deposits, DEPOSIT_TTL_SECONDS)
    now = datetime.now().timestamp()

    for _ in range(200):
        dep = random.randint(min_val, max_val)
        if dep not in used_deposits:
            used_deposits[dep] = now
            return dep

    oldest_val = min(used_deposits.items(), key=lambda x: x[1])[0]
    used_deposits[oldest_val] = now
    return oldest_val

def _unique_profit(candidate_fn) -> int:
    """Generate a profit that isn't in recent DB rows or recent cooldown."""
    _prune_used(used_profits, PROFIT_TTL_SECONDS)
    now = datetime.now().timestamp()
    recent = fetch_recent_profits()

    for _ in range(500):
        raw = candidate_fn()
        prof = int(raw // 50 * 50)
        if prof not in recent and prof not in used_profits:
            used_profits[prof] = now
            return prof

    if used_profits:
        oldest_val = min(used_profits.items(), key=lambda x: x[1])[0]
        used_profits[oldest_val] = now
        return oldest_val

    return int(candidate_fn() // 50 * 50)

# Setup logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "profit_flex_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STOCK_SYMBOLS = [s.strip() for s in os.getenv("STOCK_SYMBOLS", "TSLA,AAPL,NVDA,MSFT,AMZN,GOOGL,META").split(",")]
CRYPTO_SYMBOLS = [s.strip() for s in os.getenv("CRYPTO_SYMBOLS", "BTC,ETH,SOL").split(",")]
MEME_COINS = [s.strip() for s in os.getenv("MEME_COINS", "NIKY").split(",")]
ALL_SYMBOLS = STOCK_SYMBOLS + CRYPTO_SYMBOLS + MEME_COINS
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///profit_flex.db")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://optionstradinguni.online/")
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "5"))
IMAGE_DIR = os.getenv("IMAGE_DIR", "images/")

VERSION = "1.0"  # Update this when pushing new code to trigger refresh

# Init DB
engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

rankings_cache = Table(
    "rankings_cache", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("content", String),  # Stores JSON string
    Column("timestamp", DateTime),
    extend_existing=True
)

posts = Table(
    "posts", metadata,
    Column("id", Integer, primary_key=True),
    Column("symbol", String),
    Column("content", String),
    Column("deposit", Float),
    Column("profit", Float),
    Column("posted_at", DateTime),
    Column("trader_id", String),  # Added trader_id column
)

users = Table(
    "users", metadata,
    Column("user_id", String, primary_key=True),
    Column("username", String),
    Column("display_name", String),
    Column("wins", Integer),
    Column("total_trades", Integer),
    Column("total_profit", Float, default=0),
    Column("last_login", DateTime),
    Column("login_streak", Integer, default=0)
)

success_stories = Table(
    "success_stories", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_name", String, unique=True),
    Column("gender", String),
    Column("story", String),
    Column("image", String)
)

hall_of_fame = Table(
    "hall_of_fame", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_name", String),
    Column("profit", Float),
    Column("scope", String),  # daily, weekly, monthly
    Column("timestamp", DateTime)
)

trader_metadata = Table(
    "trader_metadata", metadata,
    Column("trader_id", String, primary_key=True),
    Column("country", String),
    Column("win_streak", Integer, default=0),
    Column("level", String, default="Rookie"),  # Rookie, Pro, Whale, Legend
    Column("total_deposit", Float, default=0.0),
    Column("total_profit", Float, default=0.0),
    Column("achievements", String)  # Comma-separated list of badges
)

trending_tickers = Table(
    "trending_tickers", metadata,
    Column("symbol", String, primary_key=True),
    Column("count", Integer, default=0),
    Column("last_posted", DateTime)
)

config = Table(
    "config", metadata,
    Column("key", String, primary_key=True),
    Column("value", String)
)

metadata.create_all(engine)

# Check and refresh database if version changed
with engine.begin() as conn:
    current_version = conn.execute(select(config.c.value).where(config.c.key == "version")).scalar()
    if current_version != VERSION:
        # Refresh tables
        conn.execute(text("DELETE FROM posts"))
        conn.execute(text("DELETE FROM trader_metadata"))
        conn.execute(text("DELETE FROM hall_of_fame"))
        logger.info("Refreshed database tables for new version.")
        conn.execute(
            insert(config).values(key="version", value=VERSION).on_conflict_do_update(
                index_elements=['key'],
                set_={"value": VERSION}
            )
        )

# Bot instance
bot = Bot(token=TELEGRAM_TOKEN)

SUCCESS_TRADERS = {
    "male": [
        ("JohnDoeTrader", "John Doe", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male1.jpeg"),
        ("AlexJohnson", "Alex Johnson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male2.jpeg"),
        ("MichaelBrown", "Michael Brown", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male3.jpeg"),
        ("DavidMiller", "David Miller", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male4.jpeg"),
        ("ChrisAnderson", "Chris Anderson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male5.jpeg")
    ],
    "female": [
        ("JaneSmithPro", "Jane Smith", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female1.jpeg"),
        ("EmilyDavis", "Emily Davis", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female2.jpeg"),
        ("SarahWilson", "Sarah Wilson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female3.jpeg"),
        ("LauraTaylor", "Laura Taylor", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female4.jpeg"),
        ("AnnaMartinez", "Anna Martinez", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female5.jpeg")
    ]
}

SUCCESS_STORY_TEMPLATES = {
    "male": [
        "transformed a modest ${deposit} investment into an impressive ${profit} through a meticulously planned swing trade on AAPL.",
        "turned ${deposit} into a remarkable ${profit} by mastering the art of BTC HODL.",
        "flipped a ${deposit} stake into ${profit} with a bold NIKY pump riding move.",
        "achieved a stunning ${profit} profit from a strategic ETH DCA plan starting with ${deposit}.",
        "earned ${profit} through a clever SOL arbitrage play after investing ${deposit}."
    ],
    "female": [
        "grew a ${deposit} investment into ${profit} with a disciplined TSLA scalping strategy.",
        "boosted ${deposit} into ${profit} with an early sniping move on DOGE.",
        "turned ${deposit} into ${profit} via a SHIB community flip.",
        "made ${profit} from a NVDA position trade starting with ${deposit}.",
        "grew ${deposit} into ${profit} with a GOOGL day trading plan."
    ]
}

NEWS_CATALYSTS = {
    "stocks": [
        "surges after strong earnings report!",
        "climbs on analyst upgrade!",
        "rallies due to new product launch!",
        "gains traction after partnership news!",
        "spikes on positive market sentiment!"
    ],
    "crypto": [
        "pumps after whale accumulation!",
        "rises on adoption news!",
        "surges with new protocol upgrade!",
        "gains after exchange listing!",
        "spikes on DeFi integration news!"
    ],
    "meme_coins": [
        "moons after viral tweet!",
        "pumps on community hype!",
        "surges with influencer endorsement!",
        "rockets after Reddit buzz!",
        "spikes on meme-driven volume!"
    ]
}

COUNTRIES = ["USA", "Nigeria", "UK", "Japan", "India", "China", "Russia", "Brazil", "Germany", "France"]

def initialize_stories():
    global TRADER_STORIES
    with engine.begin() as conn:
        existing = conn.execute(success_stories.select()).fetchall()
        if existing:
            logger.info("Loaded success stories from DB.")
            stories = {"male": [], "female": []}
            for row in existing:
                stories[row.gender].append({
                    "name": row.trader_name,
                    "story": row.story,
                    "image": row.image
                })
            TRADER_STORIES = stories
            return stories

        logger.info("Generating new success stories...")
        stories = {"male": [], "female": []}

        deposits = [300, 400, 500, 600, 700, 800, 1000, 1200, 1500, 2000]
        random.shuffle(deposits)

        profits_used = set()

        for gender, traders in SUCCESS_TRADERS.items():
            for _, name, image_url in traders:
                deposit = deposits.pop()
                profit = None
                while not profit or profit in profits_used:
                    raw_profit = deposit * random.uniform(2, 8)
                    round_base = random.choice([50, 100])
                    profit = int(round(raw_profit / round_base) * round_base)
                profits_used.add(profit)

                deposit_str = f"${deposit:,}"
                profit_str = f"${profit:,}"

                template = random.choice(SUCCESS_STORY_TEMPLATES[gender])
                story_text = f"{name} {template.replace('${deposit}', deposit_str).replace('${profit}', profit_str)}"

                conn.execute(success_stories.insert().values(
                    trader_name=name,
                    gender=gender,
                    story=story_text,
                    image=image_url
                ))

                stories[gender].append({
                    "name": name,
                    "story": story_text,
                    "image": image_url
                })

        TRADER_STORIES = stories
        return stories

def initialize_trader_metadata():
    with engine.begin() as conn:
        existing = conn.execute(select(trader_metadata)).fetchall()
        if existing:
            logger.info("Trader metadata already initialized.")
            return

        logger.info("Initializing trader metadata...")
        for trader_id, trader_name in RANKING_TRADERS:
            total_profit = random.randint(2000, 30000) // 50 * 50
            conn.execute(trader_metadata.insert().values(
                trader_id=trader_id,
                country=random.choice(COUNTRIES),
                win_streak=0,
                level="Rookie",
                total_deposit=0.0,
                total_profit=total_profit,
                achievements=""
            ))
            update_trader_level(trader_id, total_profit)

TRADER_STORIES = initialize_stories()
RANKING_TRADERS = [
    ('laurajohnson', 'Laura Johnson'), ('jennifergonzalez', 'Jennifer Gonzalez'), ('sarahhernandez', 'Sarah Hernandez'), ('josephtaylor', 'Joseph Taylor'), ('lindajackson', 'Linda Jackson'), ('matthewlopez', 'Matthew Lopez'), ('josephdavis', 'Joseph Davis'), ('matthewsmith', 'Matthew Smith'), ('jenniferhernandez', 'Jennifer Hernandez'), ('davidjones', 'David Jones'), ('christophermoore', 'Christopher Moore'), ('christopherthomas', 'Christopher Thomas'), ('christopherwilson', 'Christopher Wilson'), ('lindahernandez', 'Linda Hernandez'), ('matthewhernandez', 'Matthew Hernandez'), ('williamrodriguez', 'William Rodriguez'), ('barbarajohnson', 'Barbara Johnson'), ('christophergarcia', 'Christopher Garcia'), ('michaellopez', 'Michael Lopez'), ('sarahmartin', 'Sarah Martin'), ('williamsmith', 'William Smith'), ('jessicamartinez', 'Jessica Martinez'), ('sarahjones', 'Sarah Jones'), ('matthewtaylor', 'Matthew Taylor'), ('marywilson', 'Mary Wilson'), ('sarahgonzalez', 'Sarah Gonzalez'), ('sarahgarcia', 'Sarah Garcia'), ('matthewbrown', 'Matthew Brown'), ('davidrodriguez', 'David Rodriguez'), ('williamtaylor', 'William Taylor'), ('christophersmith', 'Christopher Smith'), ('johnwilson', 'John Wilson'), ('williamgarcia', 'William Garcia'), ('robertwilliams', 'Robert Williams'), ('danielgarcia', 'Daniel Garcia'), ('marymoore', 'Mary Moore'), ('christopherbrown', 'Christopher Brown'), ('danielbrown', 'Daniel Brown'), ('jessicarodriguez', 'Jessica Rodriguez'), ('jessicahernandez', 'Jessica Hernandez'), ('williamanderson', 'William Anderson'), ('michaeljohnson', 'Michael Johnson'), ('jamesmartin', 'James Martin'), ('matthewjohnson', 'Matthew Johnson'), ('christopherjones', 'Christopher Jones'), ('barbaraanderson', 'Barbara Anderson'), ('christopherwilliams', 'Christopher Williams'), ('matthewbrown', 'Matthew Brown'), ('barbarasmith', 'Barbara Smith'), ('patriciathomas', 'Patricia Thomas'), ('roberttaylor', 'Robert Taylor'), ('johnmoore', 'John Moore'), ('jessicagonzalez', 'Jessica Gonzalez'), ('patriciamiller', 'Patricia Miller'), ('elizabethbrown', 'Elizabeth Brown'), ('williamlopez', 'William Lopez'), ('lindasmith', 'Linda Smith'), ('jessicamartin', 'Jessica Martin'), ('lindamoore', 'Linda Moore'), ('robertmoore', 'Robert Moore'), ('davidjackson', 'David Jackson'), ('elizabethgarcia', 'Elizabeth Garcia'), ('jessicamiller', 'Jessica Miller'), ('jamesjohnson', 'James Johnson'), ('josephwilson', 'Joseph Wilson'), ('marysmith', 'Mary Smith'), ('jessicarodriguez', 'Jessica Rodriguez'), ('barbaramartin', 'Barbara Martin'), ('jenniferanderson', 'Jennifer Anderson'), ('johnhernandez', 'John Hernandez'), ('williamgonzalez', 'William Gonzalez'), ('williamdavis', 'William Davis'), ('marysmith', 'Mary Smith'), ('danielmiller', 'Daniel Miller'), ('patriciaanderson', 'Patricia Anderson'), ('elizabethbrown', 'Elizabeth Brown'), ('johnjohnson', 'John Johnson'), ('lauradavis', 'Laura Davis'), ('christopherwilson', 'Christopher Wilson'), ('sarahtaylor', 'Sarah Taylor'), ('williamgarcia', 'William Garcia'), ('laurajohnson', 'Laura Johnson'), ('patriciajackson', 'Patricia Jackson'), ('christopherwilliams', 'Christopher Williams'), ('barbaramartinez', 'Barbara Martinez'), ('emilythomas', 'Emily Thomas'), ('matthewmartinez', 'Matthew Martinez'), ('lauramartin', 'Laura Martin'), ('josephbrown', 'Joseph Brown'), ('christopherwilliams', 'Christopher Williams'), ('jenniferjohnson', 'Jennifer Johnson'), ('elizabethwilliams', 'Elizabeth Williams'), ('marywilson', 'Mary Wilson'), ('danielwilliams', 'Daniel Williams'), ('lauragonzalez', 'Laura Gonzalez'), ('barbarabrown', 'Barbara Brown'), ('jamesmartinez', 'James Martinez'), ('danielthomas', 'Daniel Thomas'), ('christophertaylor', 'Christopher Taylor'), ('lindamoore', 'Linda Moore'), ('lindajackson', 'Linda Jackson'), ('aminaibrahim', 'Amina Ibrahim'), ('funkenwafor', 'Funke Nwafor'), ('oluwaseunokafor', 'Oluwaseun Okafor'), ('emekaibrahim', 'Emeka Ibrahim'), ('oluchieze', 'Oluchi Eze'), ('kehindeokeke', 'Kehinde Okeke'), ('sadiqokoye', 'Sadiq Okoye'), ('adebayookafor', 'Adebayo Okafor'), ('emekayusuf', 'Emeka Yusuf'), ('chikaojo', 'Chika Ojo'), ('fatimaokoro', 'Fatima Okoro'), ('kehindeahmed', 'Kehinde Ahmed'), ('bolaeze', 'Bola Eze'), ('oluchiibrahim', 'Oluchi Ibrahim'), ('ifeomaokoro', 'Ifeoma Okoro'), ('tundesani', 'Tunde Sani'), ('taiwoojo', 'Taiwo Ojo'), ('adebayoafolabi', 'Adebayo Afolabi'), ('oluchiadeyemi', 'Oluchi Adeyemi'), ('ucheafolabi', 'Uche Afolabi'), ('abduladeleke', 'Abdul Adeleke'), ('abdulobi', 'Abdul Obi'), ('sergeymorozov', 'Sergey Morozov'), ('natashafedorova', 'Natasha Fedorova'), ('sergeymymorozov', 'Sergey Morozov'), ('tatianakuznetsov', 'Tatiana Kuznetsov'), ('annakozlov', 'Anna Kozlov'), ('ekaterinalebedev', 'Ekaterina Lebedev'), ('olgasemenov', 'Olga Semenov'), ('olgaorlov', 'Olga Orlov'), ('svetlanalebedev', 'Svetlana Lebedev'), ('natashaalekseev', 'Natasha Alekseev'), ('irinalebedev', 'Irina Lebedev'), ('svetlanaromanov', 'Svetlana Romanov'), ('nikolaisokolov', 'Nikolai Sokolov'), ('irinakuznetsov', 'Irina Kuznetsov'), ('alexeyegorov', 'Alexey Egorov'), ('dmitryvolkov', 'Dmitry Volkov'), ('mikhailorlov', 'Mikhail Orlov'), ('tatianaalekseev', 'Tatiana Alekseev'), ('tatianaegorov', 'Tatiana Egorov'), ('mikhailpavlov', 'Mikhail Pavlov'), ('annakozlov', 'Anna Kozlov'), ('elenafedorov', 'Elena Fedorov'), ('natashakuznetsov', 'Natasha Kuznetsov'), ('olgafedorov', 'Olga Fedorov'), ('elenasokolov', 'Elena Sokolov'), ('pavelromanov', 'Pavel Romanov'), ('igorsokolov', 'Igor Sokolov'), ('sergeypetrov', 'Sergey Petrov'), ('tatianakuznetsov', 'Tatiana Kuznetsov'), ('svetlanamorozov', 'Svetlana Morozov'), ('natashapavlov', 'Natasha Pavlov'), ('alexeymorozov', 'Alexey Morozov'), ('ivansmirnov', 'Ivan Smirnov'), ('natashapavlov', 'Natasha Pavlov'), ('dmitrykovalenko', 'Dmitry Kovalenko'), ('sergeystepanov', 'Sergey Stepanov'), ('irinapopov', 'Irina Popov'), ('alexeypetrov', 'Alexey Petrov'), ('svetlanaalekseev', 'Svetlana Alekseev'), ('pavelnovikov', 'Pavel Novikov'), ('vladimirlebedev', 'Vladimir Lebedev'), ('sergeymorozov', 'Sergey Morozov'), ('natashaorlov', 'Natasha Orlov'), ('alexeyfedorov', 'Alexey Fedorov'), ('alexeysmirnov', 'Alexey Smirnov'), ('ivannovikov', 'Ivan Novikov'), ('ekaterinalebedev', 'Ekaterina Lebedev'), ('igorpopov', 'Igor Popov'), ('ivanivanov', 'Ivan Ivanov'), ('ekaterinapopov', 'Ekaterina Popov'), ('olgalebedev', 'Olga Lebedev'), ('mariakozlov', 'Maria Kozlov'), ('dmitrymorozov', 'Dmitry Morozov'), ('andreimorozov', 'Andrei Morozov'), ('ivannovikov', 'Ivan Novikov'), ('mikhailalekseev', 'Mikhail Alekseev'), ('svetlanakovalenko', 'Svetlana Kovalenko'), ('elenaorlov', 'Elena Orlov'), ('pavelivanov', 'Pavel Ivanov'), ('nikolaipavlov', 'Nikolai Pavlov'), ('alexeysmirnov', 'Alexey Smirnov'), ('alexeysokolov', 'Alexey Sokolov'), ('ivannovikov', 'Ivan Novikov'), ('igorsmirnov', 'Igor Smirnov'), ('olgastepanov', 'Olga Stepanov'), ('annamorozov', 'Anna Morozov'), ('igorsokolov', 'Igor Sokolov'), ('ivanfedorov', 'Ivan Fedorov'), ('svetlanaorlov', 'Svetlana Orlov'), ('marinanovikov', 'Marina Novikov'), ('natashaorlov', 'Natasha Orlov'), ('dmitrysokolov', 'Dmitry Sokolov'), ('annaegorov', 'Anna Egorov'), ('igorfedorov', 'Igor Fedorov'), ('marinaegorov', 'Marina Egorov'), ('mariaorlov', 'Maria Orlov'), ('elenasokolov', 'Elena Sokolov'), ('irinakozlov', 'Irina Kozlov'), ('annasokolov', 'Anna Sokolov'), ('ivankovalenko', 'Ivan Kovalenko'), ('gabrielpereira', 'Gabriel Pereira'), ('gabrielrodrigues', 'Gabriel Rodrigues'), ('pedrocardoso', 'Pedro Cardoso'), ('anasilva', 'Ana Silva'), ('pedroribeiro', 'Pedro Ribeiro'), ('beatrizsantos', 'Beatriz Santos'), ('pedrocardoso', 'Pedro Cardoso'), ('rafaelsouza', 'Rafael Souza'), ('luizagomes', 'Luiza Gomes'), ('pedromendes', 'Pedro Mendes'), ('carlossantos', 'Carlos Santos'), ('rafaelcardoso', 'Rafael Cardoso'), ('julianabarbosa', 'Juliana Barbosa'), ('diegom Carvalho', 'Diego Carvalho'), ('julianaoliveira', 'Juliana Oliveira'), ('carlosoliveira', 'Carlos Oliveira'), ('josealves', 'Jose Alves'), ('beatrizcarvalho', 'Beatriz Carvalho'), ('beatrizcardoso', 'Beatriz Cardoso'), ('fernandaferreira', 'Fernanda Ferreira'), ('gabriellima', 'Gabriel Lima'), ('rafaelsilva', 'Rafael Silva'), ('lucasribeiro', 'Lucas Ribeiro'), ('carlosaraujo', 'Carlos Araujo'), ('sophiaaraujo', 'Sophia Araujo'), ('ricardoribeiro', 'Ricardo Ribeiro'), ('camilamartins', 'Camila Martins'), ('sophiacavalcanti', 'Sophia Cavalcanti'), ('fernandasouza', 'Fernanda Souza'), ('pedrogomes', 'Pedro Gomes'), ('carlosbarbosa', 'Carlos Barbosa'), ('pedroribeiro', 'Pedro Ribeiro'), ('ricardoaraujo', 'Ricardo Araujo'), ('fernandanunes', 'Fernanda Nunes'), ('larissaribeiro', 'Larissa Ribeiro'), ('joaomartins', 'Joao Martins'), ('joaocarvalho', 'Joao Carvalho'), ('sophiasouza', 'Sophia Souza'), ('fernandamartins', 'Fernanda Martins'), ('rafaellima', 'Rafael Lima'), ('julianarodrigues', 'Juliana Rodrigues'), ('ricardosilva', 'Ricardo Silva'), ('gabrielcavalcanti', 'Gabriel Cavalcanti'), ('luizalima', 'Luiza Lima'), ('jose Lima', 'Jose Lima'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa Oliveira'), ('carloslima', 'Carlos Lima'), ('rafaelnunes', 'Rafael Nunes'), ('fernandaferreira', 'Fernanda Ferreira'), ('joseferreira', 'Jose Ferreira'), ('mariacosta', 'Maria Costa'), ('luizaaraujo', 'Luiza Araujo'), ('larissasilva', 'Larissa Silva'), ('patriciacosta', 'Patricia Costa'), ('luizamartins', 'Luiza Martins'), ('larissaoliveira', 'Larissa oliveira'),
    # (truncated for brevity, the full list from the tool output is here)
]

def update_trader_level(trader_id, total_profit):
    level = "Rookie"
    if total_profit is None:
        total_profit = 0
    if total_profit >= 100000:
        level = "Legend"
    elif total_profit >= 50000:
        level = "Whale"
    elif total_profit >= 10000:
        level = "Pro"
    with engine.begin() as conn:
        conn.execute(
            update(trader_metadata).where(trader_metadata.c.trader_id == trader_id).values(level=level)
        )

def initialize_posts():
    with engine.begin() as conn:
        existing = conn.execute(select(posts)).fetchall()
        if existing:
            logger.info("Posts already initialized.")
            return

        logger.info("Initializing fake posts...")
        for _ in range(200):
            symbol = random.choice(ALL_SYMBOLS)
            trader_id, _ = random.choice(RANKING_TRADERS)
            deposit = random.randint(100, 40000)
            profit = deposit * random.uniform(2, 8) if random.random() < 0.95 else -random.randint(500, 1200)
            posted_at = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))
            conn.execute(insert(posts).values(
                symbol=symbol,
                content="Fake post for initialization",
                deposit=deposit,
                profit=profit,
                posted_at=posted_at,
                trader_id=trader_id
            ))
            if profit > 0:
                conn.execute(
                    update(trader_metadata).where(trader_metadata.c.trader_id == trader_id).values(
                        total_profit=trader_metadata.c.total_profit + profit,
                        total_deposit=trader_metadata.c.total_deposit + deposit,
                        win_streak=trader_metadata.c.win_streak + 1
                    )
                )
                total_profit = conn.execute(
                    select(trader_metadata.c.total_profit).where(trader_metadata.c.trader_id == trader_id)
                ).scalar() or 0
                update_trader_level(trader_id, total_profit)
                win_streak = conn.execute(
                    select(trader_metadata.c.win_streak).where(trader_metadata.c.trader_id == trader_id)
                ).scalar() or 0
                assign_achievements(trader_id, profit, deposit, win_streak)

initialize_posts()

def assign_achievements(trader_id, profit, deposit, win_streak):
    achievements = []
    if profit / max(deposit, 1) > 20:
        achievements.append("Moonshot King")
    if deposit >= 20000:
        achievements.append("Whale")
    if win_streak >= 5:
        achievements.append("Streak Master")
    if profit >= 10000:
        achievements.append("Big Winner")
    if random.random() < 0.05:
        achievements.append("Diamond Hands")
    with engine.begin() as conn:
        existing = conn.execute(select(trader_metadata.c.achievements).where(trader_metadata.c.trader_id == trader_id)).scalar() or ""
        current_achievements = set(existing.split(",")).union(achievements)
        conn.execute(
            update(trader_metadata).where(trader_metadata.c.trader_id == trader_id).values(achievements=",".join(current_achievements))
        )
    return achievements

def generate_profit_scenario(symbol):
    recent_profits = fetch_recent_profits()
    is_loss = random.random() < 0.05  # 5% chance of flash crash

    if symbol in MEME_COINS:
        deposit = _unique_deposit(500, 7000)
        if is_loss:
            profit = -random.randint(500, 1200)
            mult = profit / deposit
        else:
            mult = random.uniform(5, 50) if random.random() < 0.90 else random.uniform(30, 100)
            profit = _unique_profit(lambda: deposit * mult)
    else:
        r = random.random()
        if r < 0.35:
            deposit = _unique_deposit(100, 900)
            mult_low, mult_high = 2.0, 8.0
        elif r < 0.85:
            deposit = _unique_deposit(500, 8500)
            mult_low, mult_high = 2.0, 8.0
        else:
            deposit = _unique_deposit(20000, 40000)
            mult_low, mult_high = 2.0, 5.0
        if is_loss:
            profit = -random.randint(500, 1200)
            mult = profit / deposit
        else:
            mult = random.uniform(mult_low, mult_high)
            profit = _unique_profit(lambda: deposit * mult)

    percentage_gain = round((profit / deposit - 1) * 100, 1) if not is_loss else round(profit / deposit * 100, 1)

    # Update trending tickers (SQLite-compatible)
    with engine.begin() as conn:
        existing = conn.execute(
            select(trending_tickers.c.count, trending_tickers.c.last_posted)
            .where(trending_tickers.c.symbol == symbol)
        ).fetchone()
        if existing:
            count, last_posted = existing
            conn.execute(
                update(trending_tickers)
                .where(trending_tickers.c.symbol == symbol)
                .values(count=count + 1, last_posted=datetime.now(timezone.utc))
            )
        else:
            conn.execute(
                insert(trending_tickers).values(
                    symbol=symbol,
                    count=1,
                    last_posted=datetime.now(timezone.utc)
                )
            )

    if symbol in STOCK_SYMBOLS:
        trading_style = random.choice(["Scalping", "Day Trading", "Swing Trade", "Position Trade"])
        reasons = [
            f"{symbol} {trading_style} {'crashed' if is_loss else 'climbed'} on momentum!",
            f"Solid {trading_style} execution on {symbol}.",
            f"{symbol} {'dipped' if is_loss else 'strength'} confirmed by clean {trading_style}.",
            f"Market {'punished' if is_loss else 'favored'} {symbol} with strong {trading_style}.",
            f"{trading_style} on {symbol} {'failed' if is_loss else 'delivered'} high quality entries."
        ]
    elif symbol in CRYPTO_SYMBOLS:
        trading_style = random.choice(["HODL", "Swing Trade", "DCA", "Arbitrage", "Leverage Trading"])
        reasons = [
            f"{symbol} {trading_style} {'crashed' if is_loss else 'rode a liquidity wave'}.",
            f"{trading_style} on {symbol} {'missed' if is_loss else 'aligned with trend expansion'}.",
            f"{symbol} {'sell-off' if is_loss else 'breakout'} + {trading_style} risk control.",
            f"Clean {trading_style} structure {'hurt' if is_loss else 'lifted'} {symbol}.",
            f"{symbol} {'plunged' if is_loss else 'trend leg advanced'} with disciplined {trading_style}."
        ]
    else:
        trading_style = random.choice(["Early Sniping", "Pump Riding", "Community Flip", "Airdrop Hunt"])
        reasons = [
            f"{symbol} {'crashed' if is_loss else 'squeeze extended'} with {trading_style}.",
            f"Community {'dumped' if is_loss else 'traction sent'} {symbol} {'lower' if is_loss else 'higher'}.",
            f"{symbol} {'tanked' if is_loss else 'trend pop'} after fresh flows.",
            f"Smart {trading_style} timing on {symbol} {'failed' if is_loss else 'worked'}.",
            f"{symbol} {'crashed' if is_loss else 'leg-up'} after catalysts and chatter."
        ]

    catalyst_type = "meme_coins" if symbol in MEME_COINS else "crypto" if symbol in CRYPTO_SYMBOLS else "stocks"
    news_catalyst = random.choice(NEWS_CATALYSTS[catalyst_type]) if not is_loss else "hit by sudden market volatility!"
    reason = f"{random.choice(reasons)} ({news_catalyst}) (+{percentage_gain}%{' loss' if is_loss else ''})"

    return deposit, profit, percentage_gain, reason, trading_style, is_loss

def assign_badge(name, profit, deposit=1000, win_streak=0):
    badges = []
    if profit / max(deposit, 1) > 20:
        badges.append("🚀 Moonshot King")
    if deposit >= 20000:
        badges.append("🐳 Whale")
    if win_streak >= 5:
        badges.append("🔥 Streak Master")
    if profit >= 10000:
        badges.append("💰 Big Winner")
    if random.random() < 0.05:
        badges.append("💎 Diamond Hands")
    return random.choice(badges) if badges else ""

def build_rankings_snapshot(scope="overall"):
    with engine.connect() as conn:
        df = pd.read_sql(
            select(trader_metadata.c.trader_id, trader_metadata.c.total_profit),
            conn
        )
    ranking_pairs = []
    for row in df.itertuples():
        name = next((n for id, n in RANKING_TRADERS if id == row.trader_id), None)
        if name:
            ranking_pairs.append({"name": name, "profit": row.total_profit})
    ranking_pairs.sort(key=lambda x: x["profit"], reverse=True)
    return ranking_pairs[:20]

def build_asset_leaderboard(asset_type):
    symbols = MEME_COINS if asset_type == "meme" else CRYPTO_SYMBOLS if asset_type == "crypto" else STOCK_SYMBOLS
    with engine.connect() as conn:
        df = pd.read_sql(
            f"SELECT trader_id, SUM(profit) as total_profit, SUM(deposit) as total_deposit FROM posts "
            f"WHERE symbol IN ({','.join([f'\'{s}\'' for s in symbols])}) GROUP BY trader_id ORDER BY total_profit DESC LIMIT 10",
            conn
        )
    lines = []
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, row in enumerate(df.itertuples(), 1):
        name = next((n for id, n in RANKING_TRADERS if id == row.trader_id), None)
        if name:
            badge = medals.get(i, f"{i}.")
            roi = round((row.total_profit / row.total_deposit) * 100, 1) if row.total_deposit > 0 else 0
            lines.append(f"{badge} {name} — ${row.total_profit:,} profit (ROI: {roi}%)")
    return lines

def build_country_leaderboard(country):
    with engine.connect() as conn:
        df = pd.read_sql(
            f"SELECT t.trader_id, t.total_profit FROM trader_metadata t "
            f"WHERE t.country = '{country}' ORDER BY t.total_profit DESC LIMIT 10",
            conn
        )
    lines = []
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, row in enumerate(df.itertuples(), 1):
        name = next((n for id, n in RANKING_TRADERS if id == row.trader_id), None)
        if name:
            badge = medals.get(i, f"{i}.")
            lines.append(f"{badge} {name} — ${row.total_profit:,.0f}")
    return lines

def build_roi_leaderboard():
    with engine.connect() as conn:
        df = pd.read_sql(
            "SELECT trader_id, SUM(profit) as total_profit, SUM(deposit) as total_deposit FROM posts "
            "GROUP BY trader_id HAVING total_deposit > 0 ORDER BY (SUM(profit) / SUM(deposit)) DESC LIMIT 10",
            conn
        )
    lines = []
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, row in enumerate(df.itertuples(), 1):
        name = next((n for id, n in RANKING_TRADERS if id == row.trader_id), None)
        if name:
            roi = round((row.total_profit / row.total_deposit) * 100, 1)
            badge = medals.get(i, f"{i}.")
            lines.append(f"{badge} {name} — {roi}% ROI (${row.total_profit:,})")
    return lines

async def fetch_cached_rankings(new_name=None, new_profit=None, app=None, scope="overall"):
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        row = conn.execute(select(rankings_cache).where(rankings_cache.c.id == 1)).fetchone()
        refresh_needed = False
        ranking_pairs = []

        if row:
            ts = row.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ranking_pairs = json.loads(row.content)
            if (now - ts) >= timedelta(hours=5):
                refresh_needed = True

        if not row or refresh_needed:
            ranking_pairs = build_rankings_snapshot(scope)
            conn.execute(delete(rankings_cache).where(rankings_cache.c.id == 1))
            conn.execute(insert(rankings_cache).values(
                id=1,
                content=json.dumps(ranking_pairs),
                timestamp=now
            ))

        elif new_name and new_profit:
            try:
                ranking_pairs.append({"name": new_name, "profit": new_profit})
                ranking_pairs.sort(key=lambda x: x["profit"], reverse=True)
                ranking_pairs = ranking_pairs[:20]
                conn.execute(delete(rankings_cache).where(rankings_cache.c.id == 1))
                conn.execute(insert(rankings_cache).values(
                    id=1,
                    content=json.dumps(ranking_pairs),
                    timestamp=now
                ))

                if app:
                    await app.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=f"🔥 BREAKING: {new_name} entered Top 20 with ${new_profit:,} profit!",
                        parse_mode=constants.ParseMode.HTML
                    )
            except Exception as e:
                logger.error(f"Ranking insertion error: {e}")

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for i, entry in enumerate(ranking_pairs, start=1):
            name, total = entry["name"], entry["profit"]
            trader_id = next((id for id, n in RANKING_TRADERS if n == name), None)
            if trader_id:
                with engine.connect() as conn:
                    trader_data = conn.execute(
                        select(trader_metadata.c.level, trader_metadata.c.win_streak, trader_metadata.c.country)
                        .where(trader_metadata.c.trader_id == trader_id)
                    ).fetchone() or ("Rookie", 0, "Unknown")
                level, win_streak, country = trader_data
                badge = medals.get(i, f"{i}.")
                extra = assign_badge(name, total, win_streak=win_streak)
                badge_text = f" {extra} ({level}, {country})" if extra else f" ({level}, {country})"
                lines.append(f"{badge} {name} — ${total:,.0f} profit{badge_text}")
        return lines

async def craft_profit_message(symbol, deposit, profit, percentage_gain, reason, trading_style, is_loss, social_lines=None):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    multiplier = round(profit / deposit, 1) if not is_loss else round(profit / deposit, 2)

    if social_lines is None:
        social_lines = await fetch_cached_rankings()

    social_text = "\n".join(social_lines[:5])
    mention = random.choice(RANKING_TRADERS)[1]
    tag = "#MemeCoinGains #CryptoTrends" if symbol in MEME_COINS else "#StockMarket #CryptoWins"
    asset_desc = "Meme Coin" if symbol in MEME_COINS else symbol

    trader_id, trader_name = random.choice(RANKING_TRADERS)
    with engine.connect() as conn:
        streak = conn.execute(
            select(trader_metadata.c.win_streak).where(trader_metadata.c.trader_id == trader_id)
        ).scalar() or 0
    streak_text = f"\n🔥 {trader_name} is on a {streak}-trade win streak!" if streak >= 3 and not is_loss else ""

    msg = (
        f"{'📉' if is_loss else '📈'} {symbol} {'Loss' if is_loss else 'Profit'} Update {'😱' if is_loss else '📈'}\n"
        f"{trading_style} on {asset_desc}\n"
        f"💰 Invested: ${deposit:,.2f}\n"
        f"{'📉' if is_loss else '🎯'} {multiplier}x Return → {'Loss' if is_loss else 'Realized'}: ${abs(profit):,.2f}\n"
        f"{'🚨' if is_loss else '🔥'} {reason}\n"
        f"📊 {'Lost' if is_loss else 'Achieved'} {abs(percentage_gain)}% {'Loss' if is_loss else 'ROI'}!\n"
        f"Time: {ts}\n{streak_text}\n\n"
        f"🏆 Top Trader Rankings:\n{social_text}\n"
        f"👉 Shoutout to {mention} for inspiring us!\n\n"
        f"Join us at {WEBSITE_URL} for more insights! {tag}"
    )

    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Visit Website", url=WEBSITE_URL)],
        [InlineKeyboardButton("🔥 React", callback_data="react_fire"),
         InlineKeyboardButton("🚀 React", callback_data="react_rocket"),
         InlineKeyboardButton("😱 React", callback_data="react_shock")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return msg, reply_markup, trader_id, trader_name

def craft_success_story(current_index, gender):
    combined = [("male", s) for s in TRADER_STORIES["male"]] + [("female", s) for s in TRADER_STORIES["female"]]
    total = len(combined)
    current_index = current_index % total
    gender, story_data = combined[current_index]

    story = story_data["story"]
    image_url = story_data["image"]

    keyboard = [
        [InlineKeyboardButton("⬅️ Prev", callback_data=f"success_prev_{gender}_{current_index}")],
        [InlineKeyboardButton("➡️ Next", callback_data=f"success_next_{gender}_{current_index}")],
        [InlineKeyboardButton("Back to Menu", callback_data="back")]
    ]

    return story, InlineKeyboardMarkup(keyboard), image_url

async def craft_trade_status():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    social_lines = await fetch_cached_rankings()
    greed_fear = random.randint(0, 100)
    mood = "🐂 Bullish" if greed_fear > 60 else "🐻 Bearish" if greed_fear < 40 else "🟡 Neutral"
    return (
        f"🏆 Top Trader Rankings 🏆\n"
        f"As of {ts}:\n"
        f"{'\n'.join(social_lines)}\n\n"
        f"📊 Market Mood: {mood} (Greed/Fear: {greed_fear}/100)\n"
        f"Join the community at {WEBSITE_URL}! #TradingCommunity"
    ), InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="back"),
         InlineKeyboardButton("Country Leaderboard", callback_data="country_leaderboard")],
        [InlineKeyboardButton("Asset Leaderboard", callback_data="asset_leaderboard")]
    ])

def craft_market_recap():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    top_symbol = pd.read_sql(
        "SELECT symbol, COUNT(*) as count FROM posts WHERE posted_at >= :start GROUP BY symbol ORDER BY count DESC LIMIT 1",
        engine,
        params={"start": datetime.now(timezone.utc) - timedelta(days=1)}
    )
    top_symbol = top_symbol.iloc[0]["symbol"] if not top_symbol.empty else random.choice(ALL_SYMBOLS)
    return (
        f"📊 Daily Market Recap 📊\n"
        f"As of {ts}:\n"
        f"🔥 Top Asset: {top_symbol} dominated with the most trades!\n"
        f"Join {WEBSITE_URL} to catch the next wave! #MarketRecap"
    ), InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]])

def craft_trending_ticker_alert():
    with engine.connect() as conn:
        df = pd.read_sql(
            "SELECT symbol, count FROM trending_tickers WHERE count >= 3 ORDER BY count DESC LIMIT 1",
            conn
        )
    if df.empty:
        return None, None
    symbol, count = df.iloc[0]["symbol"], df.iloc[0]["count"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"🚨 Trending Ticker Alert 🚨\n"
        f"{symbol} appeared {count} times today!\n"
        f"Time: {ts}\n"
        f"Jump in at {WEBSITE_URL}! #TrendingTicker"
    ), InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]])

def log_post(symbol, content, deposit, profit, user_id=None, trader_id=None):
    try:
        with engine.begin() as conn:
            if user_id:
                conn.execute(
                    update(users).where(users.c.user_id == user_id).values(total_profit=users.c.total_profit + profit)
                )
            if trader_id and profit > 0:
                conn.execute(
                    update(trader_metadata).where(trader_metadata.c.trader_id == trader_id).values(
                        total_profit=trader_metadata.c.total_profit + profit,
                        total_deposit=trader_metadata.c.total_deposit + deposit,
                        win_streak=trader_metadata.c.win_streak + 1
                    )
                )
                total_profit = conn.execute(
                    select(trader_metadata.c.total_profit).where(trader_metadata.c.trader_id == trader_id)
                ).scalar() or 0
                update_trader_level(trader_id, total_profit)
                win_streak = conn.execute(
                    select(trader_metadata.c.win_streak).where(trader_metadata.c.trader_id == trader_id)
                ).scalar() or 0
                assign_achievements(trader_id, profit, deposit, win_streak)
            conn.execute(
                insert(posts).values(
                    symbol=symbol,
                    content=content,
                    deposit=deposit,
                    profit=profit,
                    posted_at=datetime.now(timezone.utc),
                    trader_id=trader_id
                )
            )
    except Exception as e:
        logger.error(f"Database error: {e}")

async def announce_winner(scope, app):
    lines = await fetch_cached_rankings(scope=scope)
    if not lines:
        return

    winner_line = lines[0]
    winner_name = winner_line.split("—")[0].split()[-1].strip("")
    winner_profit = int("".join([c for c in winner_line.split("—")[1] if c.isdigit()]))

    with engine.begin() as conn:
        conn.execute(
            insert(hall_of_fame).values(
                trader_name=winner_name,
                profit=winner_profit,
                scope=scope,
                timestamp=datetime.now(timezone.utc)
            )
        )

    msg = (
        f"🔥 {scope.capitalize()} Winner! 🏆\n"
        f"👑 {winner_name} secured ${winner_profit:,} profit!\n"
        f"Join the rankings at {WEBSITE_URL}! #Winner"
    )

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=msg,
        parse_mode=constants.ParseMode.HTML
    )

async def profit_posting_loop(app):
    logger.info("Profit posting task started.")
    last_recap = datetime.now(timezone.utc) - timedelta(days=1)
    while True:
        try:
            wait_minutes = random.choices([5,10,15,20,30,60,120], weights=[30,30,30,30,5,2,1])[0]
            wait_seconds = wait_minutes * 60
            logger.info(f"Next profit post in {wait_minutes}m at {datetime.now(timezone.utc)}")
            await asyncio.sleep(wait_seconds)

            symbol = random.choice(ALL_SYMBOLS)
            deposit, profit, percentage_gain, reason, trading_style, is_loss = generate_profit_scenario(symbol)
            trader_id, trader_name = random.choice(RANKING_TRADERS)
            msg, reply_markup, trader_id, trader_name = await craft_profit_message(
                symbol, deposit, profit, percentage_gain, reason, trading_style, is_loss
            )

            message = await app.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode=constants.ParseMode.HTML,
                reply_markup=reply_markup
            )
            logger.info(f"[PROFIT POSTED] {symbol} {trading_style} Deposit ${deposit:.2f} → {'Loss' if is_loss else 'Profit'} ${abs(profit):,.2f}")
            log_post(symbol, msg, deposit, profit, trader_id=trader_id)

            await fetch_cached_rankings(new_name=trader_name, new_profit=profit, app=app)

            if profit > 10000 and not is_loss:
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"🌟 Trade of the Day! 🌟\n{trader_name} made ${profit:,} on {symbol}!\nJoin {WEBSITE_URL}! #TradeOfTheDay",
                    parse_mode=constants.ParseMode.HTML
                )

            await asyncio.sleep(RATE_LIMIT_SECONDS)

            if random.random() < 0.2:
                status_msg, status_reply_markup = await craft_trade_status()
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=status_msg,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=status_reply_markup
                )
                logger.info("Posted trade status update.")
                log_post(None, status_msg, None, None)

            if (datetime.now(timezone.utc) - last_recap) >= timedelta(days=1):
                recap_msg, recap_reply_markup = craft_market_recap()
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=recap_msg,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=recap_reply_markup
                )
                last_recap = datetime.now(timezone.utc)

            if random.random() < 0.1:
                trend_msg, trend_reply_markup = craft_trending_ticker_alert()
                if trend_msg:
                    await app.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=trend_msg,
                        parse_mode=constants.ParseMode.HTML,
                        reply_markup=trend_reply_markup
                    )

            if random.random() < 0.05:
                poll_question = "Which asset will pump next?"
                options = random.sample(ALL_SYMBOLS, 4)
                await app.bot.send_poll(
                    chat_id=TELEGRAM_CHAT_ID,
                    question=poll_question,
                    options=options,
                    is_anonymous=False
                )

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

def main():
    if TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None:
        raise SystemExit("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in .env")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("trade_status", trade_status_handler))
    app.add_handler(CommandHandler("hall_of_fame", hall_of_fame_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    async def on_startup(app):
        app.create_task(profit_posting_loop(app))
        logger.info("Profit posting task scheduled on startup.")

    app.post_init = on_startup

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
