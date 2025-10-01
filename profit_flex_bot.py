"""
Profit Flex Bot - Real-Time Trading Insights
Delivers authentic profit scenarios for stocks, crypto, and meme coins every 20-40 minutes.
- Stocks/Crypto: Realistic gains (10%-200%).
- Meme Coins: Higher gains (100%-900%).
Powered by a community of winning traders with real names.
Includes success stories and mentions for engagement.
"""



import os
import random
import asyncio
import logging
from sqlalchemy import select, delete, insert
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
PROFIT_TTL_SECONDS  = 12 * 60 * 60    # 12 hours

def _prune_used(used_dict: dict[int, float], ttl_seconds: int) -> None:
    """Remove entries older than ttl_seconds."""
    now = datetime.now().timestamp()
    stale = [v for v, ts in used_dict.items() if (now - ts) > ttl_seconds]
    for v in stale:
        used_dict.pop(v, None)

def _unique_deposit(min_val: int, max_val: int) -> int:
    """
    Return a deposit that hasn't been used recently.
    No rounding — leaves 'organic' numbers like 817, 1045, etc.
    """
    _prune_used(used_deposits, DEPOSIT_TTL_SECONDS)
    now = datetime.now().timestamp()

    # Try a bunch of times to get a fresh one
    for _ in range(200):
        dep = random.randint(min_val, max_val)
        if dep not in used_deposits:
            used_deposits[dep] = now
            return dep

    # Fallback: allow reuse of the least-recently used value
    oldest_val = min(used_deposits.items(), key=lambda x: x[1])[0]
    used_deposits[oldest_val] = now
    return oldest_val

def _unique_profit(candidate_fn) -> int:
    """
    Generate a profit that isn't in recent DB rows or recent cooldown.
    Rounds to the nearest 50 to look realistic.
    """
    _prune_used(used_profits, PROFIT_TTL_SECONDS)
    now = datetime.now().timestamp()
    recent = fetch_recent_profits()  # your existing DB helper

    for _ in range(500):
        raw = candidate_fn()
        prof = int(raw // 50 * 50)
        if prof not in recent and prof not in used_profits:
            used_profits[prof] = now
            return prof

    # Fallback: reuse the least-recently used profit
    if used_profits:
        oldest_val = min(used_profits.items(), key=lambda x: x[1])[0]
        used_profits[oldest_val] = now
        return oldest_val

    # Last resort if everything else failed
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

# Init DB
engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

rankings_cache = Table(
    "rankings_cache", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("content", String),
    Column("timestamp", DateTime),
    Column("scope", String)  # "daily", "weekly", "monthly"
)

posts = Table(
    "posts", metadata,
    Column("id", Integer, primary_key=True),
    Column("symbol", String),
    Column("content", String),
    Column("deposit", Float),
    Column("profit", Float),
    Column("posted_at", DateTime)
)

users = Table(
    "users", metadata,
    Column("user_id", String, primary_key=True),
    Column("username", String),
    Column("display_name", String),
    Column("wins", Integer),
    Column("total_trades", Integer),
    Column("total_profit", Float, default=0)
)

success_stories = Table(
    "success_stories", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trader_name", String, unique=True),
    Column("gender", String),
    Column("story", String),
    Column("image", String)
)

# Rankings cache table
rankings_cache = Table(
    "rankings_cache", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("content", String),
    Column("timestamp", DateTime)
)

metadata.create_all(engine)

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

# Story templates
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

def initialize_stories():
    with engine.begin() as conn:
        existing = conn.execute(success_stories.select()).fetchall()
        if existing:
            logger.info("Loaded success stories from DB.")
            stories = {"male": [], "female": []}
            for row in existing:
                stories[row.gender].append({
                    "name": row.trader_name,
                    "story": row.story,
                    "image": row.image  # already a URL now
                })
            return stories

        logger.info("Generating new success stories...")
        stories = {"male": [], "female": []}

        deposits = [300, 400, 500, 600, 700, 800, 1000, 1200, 1500, 2000]
        random.shuffle(deposits)  

        profits_used = set()

        for gender, traders in SUCCESS_TRADERS.items():
            for _, name, image_url in traders:  # now we use URL directly
                deposit = deposits.pop()

                # Generate realistic profits
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
                    image=image_url  # save URL instead of local path
                ))

                stories[gender].append({
                    "name": name,
                    "story": story_text,
                    "image": image_url
                })

        return stories

TRADER_STORIES = initialize_stories()

# Expanded Trader Names for Rankings
RANKING_TRADERS = [
    # Male Traders
    ("RobertGarcia", "Robert Garcia"), ("JamesLopez", "James Lopez"),
    ("WilliamRodriguez", "William Rodriguez"), ("DanielPerez", "Daniel Perez"),
    ("MatthewRamirez", "Matthew Ramirez"), ("EthanLee", "Ethan Lee"),
    ("BenjaminScott", "Benjamin Scott"), ("LucasBaker", "Lucas Baker"),
    ("HenryAllen", "Henry Allen"), ("SamuelGreen", "Samuel Green"),
    ("ThomasClark", "Thomas Clark"), ("JosephTurner", "Joseph Turner"),
    ("NathanielReed", "Nathaniel Reed"), ("AnthonyKing", "Anthony King"),
    ("DavidWright", "David Wright"), ("ChristopherHill", "Christopher Hill"),
    ("JonathanMitchell", "Jonathan Mitchell"), ("PatrickYoung", "Patrick Young"),
    ("JasonAdams", "Jason Adams"), ("KevinRoberts", "Kevin Roberts"),
    ("RyanNelson", "Ryan Nelson"), ("BrandonWalker", "Brandon Walker"),
    ("TylerScott", "Tyler Scott"), ("ZacharyMoore", "Zachary Moore"),
    ("ConnorWhite", "Connor White"), ("ShawnHarris", "Shawn Harris"),
    ("JustinReyes", "Justin Reyes"), ("DerekParker", "Derek Parker"),
    ("LoganBarnes", "Logan Barnes"), ("MasonBrooks", "Mason Brooks"),
    ("JordanFoster", "Jordan Foster"), ("ElijahCarter", "Elijah Carter"),
    ("CalebEvans", "Caleb Evans"), ("OwenMurphy", "Owen Murphy"),
    ("GavinDiaz", "Gavin Diaz"), ("NoahHughes", "Noah Hughes"),
    ("ColeSimmons", "Cole Simmons"), ("HunterButler", "Hunter Butler"),
    ("ChaseLong", "Chase Long"), ("MicahHayes", "Micah Hayes"),
    ("AdrianRoss", "Adrian Ross"), ("VictorColeman", "Victor Coleman"),
    ("XavierMorgan", "Xavier Morgan"), ("DominicGray", "Dominic Gray"),
    ("IsaacPeterson", "Isaac Peterson"), ("LeviWard", "Levi Ward"),
    ("MilesWatson", "Miles Watson"), ("MaxwellHoward", "Maxwell Howard"),
    ("JulianPrice", "Julian Price"), ("ChristianSanders", "Christian Sanders"),
    ("LiamHenderson", "Liam Henderson"), ("NicholasGibson", "Nicholas Gibson"),
    ("DiegoFernandez", "Diego Fernandez"), ("CarlosMendez", "Carlos Mendez"),
    ("JavierOrtega", "Javier Ortega"), ("LuisCastillo", "Luis Castillo"),
    ("MateoVargas", "Mateo Vargas"), ("AndresMorales", "Andres Morales"),
    ("JoseMartinez", "Jose Martinez"), ("PedroLopez", "Pedro Lopez"),
    ("VictorSantos", "Victor Santos"), ("RicardoAlvarez", "Ricardo Alvarez"),
    ("AhmedKhalid", "Ahmed Khalid"), ("OmarHassan", "Omar Hassan"),
    ("KarimAli", "Karim Ali"), ("YoussefSalem", "Youssef Salem"),
    ("IbrahimMahmoud", "Ibrahim Mahmoud"), ("AbdulRahman", "Abdul Rahman"),
    ("MustafaFarouk", "Mustafa Farouk"), ("HassanOmar", "Hassan Omar"),
    ("KwameMensah", "Kwame Mensah"), ("ChineduOkafor", "Chinedu Okafor"),
    ("SamuelAdeyemi", "Samuel Adeyemi"), ("OluwaseunAkin", "Oluwaseun Akin"),
    ("EmekaNwosu", "Emeka Nwosu"), ("JosephBello", "Joseph Bello"),
    ("MichaelOkon", "Michael Okon"), ("DanielChukwu", "Daniel Chukwu"),
    ("KenjiTanaka", "Kenji Tanaka"), ("HiroshiYamamoto", "Hiroshi Yamamoto"),
    ("TakashiKobayashi", "Takashi Kobayashi"), ("SatoshiNakamura", "Satoshi Nakamura"),
    ("DaichiFujimoto", "Daichi Fujimoto"), ("MinHoPark", "Min Ho Park"),
    ("JaeWooKim", "Jae Woo Kim"), ("SungHoLee", "Sung Ho Lee"),
    ("HirokiSuzuki", "Hiroki Suzuki"), ("YutoMatsumoto", "Yuto Matsumoto"),
    ("RaviKumar", "Ravi Kumar"), ("ArjunPatel", "Arjun Patel"),
    ("VikramSharma", "Vikram Sharma"), ("AnilMehta", "Anil Mehta"),
    ("RajeshSingh", "Rajesh Singh"), ("SanjayGupta", "Sanjay Gupta"),
    ("ChenWei", "Chen Wei"), ("LiMing", "Li Ming"),
    ("WangJun", "Wang Jun"), ("ZhaoLei", "Zhao Lei"),
    ("SunHao", "Sun Hao"), ("ZhangYong", "Zhang Yong"),
    ("DmitriIvanov", "Dmitri Ivanov"), ("SergeiPetrov", "Sergei Petrov"),
    ("AlexeiVolkov", "Alexei Volkov"), ("ViktorSmirnov", "Viktor Smirnov"),
    ("NikolaiPopov", "Nikolai Popov"), ("AndreiSokolov", "Andrei Sokolov"),

    # Female Traders
    ("OliviaHernandez", "Olivia Hernandez"), ("SophiaGonzalez", "Sophia Gonzalez"),
    ("MiaMartinez", "Mia Martinez"), ("IsabellaSanchez", "Isabella Sanchez"),
    ("CharlotteTorres", "Charlotte Torres"), ("AvaKing", "Ava King"),
    ("GraceAdams", "Grace Adams"), ("ChloeYoung", "Chloe Young"),
    ("EllaWright", "Ella Wright"), ("VictoriaHarris", "Victoria Harris"),
    ("EmmaWhite", "Emma White"), ("LilyHall", "Lily Hall"),
    ("ZoeParker", "Zoe Parker"), ("AmeliaStewart", "Amelia Stewart"),
    ("HarperBennett", "Harper Bennett"), ("ScarlettRivera", "Scarlett Rivera"),
    ("AriaFlores", "Aria Flores"), ("LaylaGomez", "Layla Gomez"),
    ("CamilaOrtiz", "Camila Ortiz"), ("PenelopeReed", "Penelope Reed"),
    ("RileyPowell", "Riley Powell"), ("NoraCook", "Nora Cook"),
    ("LillianRogers", "Lillian Rogers"), ("HannahSimmons", "Hannah Simmons"),
    ("EvelynFoster", "Evelyn Foster"), ("StellaCole", "Stella Cole"),
    ("EllieWard", "Ellie Ward"), ("HazelPeterson", "Hazel Peterson"),
    ("AuroraGray", "Aurora Gray"), ("SavannahEvans", "Savannah Evans"),
    ("PaisleyCollins", "Paisley Collins"), ("BrooklynDiaz", "Brooklyn Diaz"),
    ("ClaireHughes", "Claire Hughes"), ("SkylarRoss", "Skylar Ross"),
    ("LucyLong", "Lucy Long"), ("BellaButler", "Bella Butler"),
    ("VioletBarnes", "Violet Barnes"), ("NaomiPrice", "Naomi Price"),
    ("MayaHoward", "Maya Howard"), ("LeahWatson", "Leah Watson"),
    ("SadieHenderson", "Sadie Henderson"), ("AliceGibson", "Alice Gibson"),
    ("EvaSanders", "Eva Sanders"), ("EverlyWard", "Everly Ward"),
    ("MadelynGray", "Madelyn Gray"), ("KinsleyMorgan", "Kinsley Morgan"),
    ("AllisonRoss", "Allison Ross"), ("AnnaHayes", "Anna Hayes"),
    ("SarahBrooks", "Sarah Brooks"), ("JuliaParker", "Julia Parker"),
    ("NatalieScott", "Natalie Scott"), ("CarolineNelson", "Caroline Nelson"),
    ("FatimaZahra", "Fatima Zahra"), ("AishaHassan", "Aisha Hassan"),
    ("LaylaAbdullah", "Layla Abdullah"), ("MariamKhalil", "Mariam Khalil"),
    ("HudaSalem", "Huda Salem"), ("AmiraFarah", "Amira Farah"),
    ("NgoziOkeke", "Ngozi Okeke"), ("AdaezeNwankwo", "Adaeze Nwankwo"),
    ("ChiomaUche", "Chioma Uche"), ("FolakeAdeola", "Folake Adeola"),
    ("FunkeOlawale", "Funke Olawale"), ("TemiBalogun", "Temi Balogun"),
    ("AkiraTanaka", "Akira Tanaka"), ("YumiKawasaki", "Yumi Kawasaki"),
    ("AyaSuzuki", "Aya Suzuki"), ("SakuraYamamoto", "Sakura Yamamoto"),
    ("NaokoFujimoto", "Naoko Fujimoto"), ("JiwooPark", "Jiwoo Park"),
    ("EunseoKim", "Eunseo Kim"), ("HanaLee", "Hana Lee"),
    ("MinaChoi", "Mina Choi"), ("SooyeonHan", "Sooyeon Han"),
    ("PriyaSharma", "Priya Sharma"), ("NehaPatel", "Neha Patel"),
    ("AnjaliKaur", "Anjali Kaur"), ("SoniaMehta", "Sonia Mehta"),
    ("RadhikaSingh", "Radhika Singh"), ("KavyaGupta", "Kavya Gupta"),
    ("LiNa", "Li Na"), ("ChenXiu", "Chen Xiu"),
    ("WangMei", "Wang Mei"), ("ZhaoLing", "Zhao Ling"),
    ("ZhangHui", "Zhang Hui"), ("SunYan", "Sun Yan"),
    ("IrinaVolkova", "Irina Volkova"), ("OlgaSmirnova", "Olga Smirnova"),
    ("NataliaPetrova", "Natalia Petrova"), ("SvetlanaIvanova", "Svetlana Ivanova"),
    ("AnastasiaSokolova", "Anastasia Sokolova"), ("ElenaMorozova", "Elena Morozova")
]

# Success story templates with dynamic placeholders
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

# Helper to fetch DB posts
def fetch_recent_profits():
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT profit FROM posts WHERE profit IS NOT NULL ORDER BY posted_at DESC LIMIT 50", conn)
            return set(df['profit'].tolist())
    except Exception as e:
        logger.error(f"Database error: {e}")
        return set()

# Helper: Generate profit scenario with realistic gains
def generate_profit_scenario(symbol):
    """
    - Meme coins: 5–50x normally; 10% chance of 30–100x 'moonshot'
      Deposits: 500–3000 (natural integers, not rounded).
    - Stocks/Crypto: 2–8x normally, but if deposit is a WHALE (20k–40k),
      cap gains tighter at 2–5x for realism.
      Deposits mix:
        • 35% small retail: 100–400
        • 50% regular: 500–1500
        • 15% whale: 20000–40000
    - Profits rounded to nearest 50; deposits are NOT rounded.
    """
    recent_profits = fetch_recent_profits()  # your existing DB check

    # --- MEME COINS (wild but believable) ---
    if symbol in MEME_COINS:
        deposit = random.randint(500, 7000)  # organic amounts like 817, 1045, etc.
        mult = random.uniform(5, 50)
        if random.random() < 0.10:  # 10% moonshot
            mult = random.uniform(30, 100)

        profit = int((deposit * mult) // 50 * 50)
        # uniqueness guard
        tries = 0
        while profit in recent_profits and tries < 10:
            mult = random.uniform(5, 50)
            if random.random() < 0.10:
                mult = random.uniform(30, 100)
            profit = int((deposit * mult) // 50 * 50)
            tries += 1

    # --- STOCKS / MAJOR CRYPTO (more conservative) ---
    else:
        r = random.random()
        if r < 0.35:                       # small retail
            deposit = random.randint(100, 900)
            mult_low, mult_high = 2.0, 8.0
        elif r < 0.85:                     # regular
            deposit = random.randint(500, 8500)
            mult_low, mult_high = 2.0, 8.0
        else:                              # whale (cap gains tighter for realism)
            deposit = random.randint(20000, 40000)
            mult_low, mult_high = 2.0, 5.0  # <-- tighter range for big capital

        mult = random.uniform(mult_low, mult_high)
        profit = int((deposit * mult) // 50 * 50)

        # uniqueness guard
        tries = 0
        while profit in recent_profits and tries < 10:
            mult = random.uniform(mult_low, mult_high)
            profit = int((deposit * mult) // 50 * 50)
            tries += 1

    # --- Narratives ---
    percentage_gain = round((profit / deposit - 1) * 100, 1)

    if symbol in STOCK_SYMBOLS:
        trading_style = random.choice(["Scalping", "Day Trading", "Swing Trade", "Position Trade"])
        reasons = [
            f"{symbol} {trading_style} climbed on momentum!",
            f"Solid {trading_style} execution on {symbol}.",
            f"{symbol} strength confirmed by clean {trading_style}.",
            f"Market favored {symbol} with strong {trading_style} follow-through.",
            f"{trading_style} on {symbol} delivered high quality entries.",
        ]
    elif symbol in CRYPTO_SYMBOLS:
        trading_style = random.choice(["HODL", "Swing Trade", "DCA", "Arbitrage", "Leverage Trading"])
        reasons = [
            f"{symbol} {trading_style} rode a liquidity wave.",
            f"{trading_style} on {symbol} aligned with trend expansion.",
            f"{symbol} breakout + {trading_style} risk control.",
            f"Clean {trading_style} structure lifted {symbol}.",
            f"{symbol} trend leg advanced with disciplined {trading_style}.",
        ]
    else:
        trading_style = random.choice(["Early Sniping", "Pump Riding", "Community Flip", "Airdrop Hunt"])
        reasons = [
            f"{symbol} squeeze extended with {trading_style}.",
            f"Community traction sent {symbol} higher.",
            f"{symbol} trend pop after fresh flows.",
            f"Smart {trading_style} timing on {symbol}.",
            f"{symbol} leg-up after catalysts and chatter.",
        ]

    reason = random.choice(reasons) + f" (+{percentage_gain}%)"
    return deposit, profit, percentage_gain, reason, trading_style

    # 🎲 Weighted multipliers: heavy tail for memes, tamer for stocks/crypto
    def weighted_multiplier(is_meme: bool) -> float:
        if is_meme:
            # Buckets (low/med/high/super) with probabilities
            buckets = [
                ( (2.0, 4.0),  0.45 ),   # most often 2–4×
                ( (4.0, 8.0),  0.30 ),   # sometimes 4–8×
                ( (8.0, 12.0), 0.18 ),   # less often 8–12×
                ( (12.0, 20.0),0.07 ),   # rare 12–20× bombs
            ]
        else:
            buckets = [
                ( (2.0, 3.0),  0.55 ),   # most often 2–3×
                ( (3.0, 4.0),  0.25 ),   # sometimes 3–4×
                ( (4.0, 5.0),  0.15 ),   # less often 4–5×
                ( (5.0, 6.0),  0.05 ),   # rare 5–6× spikes
            ]
        r = random.random()
        cum = 0.0
        for (low, high), p in buckets:
            cum += p
            if r <= cum:
                return random.uniform(low, high)
        low, high = buckets[-1][0]
        return random.uniform(low, high)

    is_meme = symbol in MEME_COINS
    deposit = random.choice(meme_deposits if is_meme else spot_deposits)

    # pick a multiplier with the weighted dist above
    mult = weighted_multiplier(is_meme)
    raw_profit = deposit * mult

    # make numbers look “human” (rounded but not too perfect)
    profit = int(raw_profit // 50 * 50)
    while profit in recent_profits:
        mult = weighted_multiplier(is_meme)
        profit = int((deposit * mult) // 50 * 50)

    multiplier = profit / deposit
    percentage_gain = round((multiplier - 1) * 100, 1)

    # price move shown in the blurb (loosely tied to ROI so it feels plausible)
    price_increase = int(percentage_gain * random.uniform(0.7, 1.1))

    if symbol in STOCK_SYMBOLS:
        trading_style = random.choice(["Scalping", "Day Trading", "Swing Trade", "Position Trade"])
        reasons = [
            f"{symbol} {trading_style} climbed {price_increase}% in a steady rally!",
            f"Solid {trading_style} on {symbol} yielded {price_increase}%!",
            f"{symbol} rose {price_increase}% on {trading_style} strategy!",
            f"Market favored {symbol} with {price_increase}% in {trading_style}!",
            f"{trading_style} on {symbol} delivered {price_increase}% returns!",
        ]
    elif symbol in CRYPTO_SYMBOLS:
        trading_style = random.choice(["HODL", "Swing Trade", "DCA", "Arbitrage", "Leverage Trading"])
        reasons = [
            f"{symbol} {trading_style} gained {price_increase}% on market trends!",
            f"{trading_style} on {symbol} secured {price_increase}%!",
            f"{symbol} increased {price_increase}% with {trading_style} approach!",
            f"Crypto {trading_style} lifted {symbol} by {price_increase}%!",
            f"Steady {price_increase}% gain on {symbol} via {trading_style}!",
        ]
    else:
        trading_style = random.choice(["Early Sniping", "Pump Riding", "Community Flip", "Airdrop Hunt"])
        reasons = [
            f"{symbol} gained {price_increase}% after a market boost!",
            f"Community drove {symbol} up {price_increase}%!",
            f"{symbol} surged {price_increase}% on trending news!",
            f"Strategic {trading_style} yielded {price_increase}% on {symbol}!",
            f"{symbol} rose {price_increase}% with smart timing!",
        ]

    return deposit, profit, percentage_gain, random.choice(reasons), trading_style

def fetch_cached_rankings(new_name=None, new_profit=None, app=None):
    """
    Returns current rankings.
    - If cache < 5h old, reuse.
    - If a new profit beats leaderboard → insert trader, re-sort, announce.
    - Full refresh every 5h.
    """
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        row = conn.execute(select(rankings_cache)).fetchone()
        refresh_needed = False
        lines = []

        if row:
            ts = row.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            lines = row.content.split("\n")

            if (now - ts) >= timedelta(hours=5):
                refresh_needed = True

        # --- Build fresh rankings if empty/expired ---
        if not row or refresh_needed:
            lines = build_rankings_snapshot()
            conn.execute(delete(rankings_cache))
            conn.execute(insert(rankings_cache).values(
                content="\n".join(lines),
                timestamp=now
            ))

        # --- Insert new trader dynamically ---
        elif new_profit and new_name:
            try:
                ranking_pairs = []
                for line in lines:
                    parts = line.split("—")
                    name = parts[0].split()[-1].strip("</b>")
                    profit = int("".join([c for c in parts[1] if c.isdigit()]))
                    ranking_pairs.append((name, profit))

                min_profit = ranking_pairs[-1][1]
                if new_profit > min_profit:
                    ranking_pairs.append((new_name, new_profit))
                    ranking_pairs.sort(key=lambda x: x[1], reverse=True)
                    ranking_pairs = ranking_pairs[:20]

                    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                    lines = []
                    for i, (name, total) in enumerate(ranking_pairs, start=1):
                        badge = medals.get(i, f"{i}.")
                        lines.append(f"{badge} <b>{name}</b> — ${total:,} profit")

                    # Save new snapshot
                    conn.execute(delete(rankings_cache))
                    conn.execute(insert(rankings_cache).values(
                        content="\n".join(lines),
                        timestamp=now
                    ))

                    # 🚨 Announce to group if app is passed
                    if app:
                        asyncio.create_task(app.bot.send_message(
                            chat_id=TELEGRAM_CHAT_ID,
                            text=f"🔥 BREAKING: <b>{new_name}</b> just entered the Top 20 with ${new_profit:,} profit!",
                            parse_mode=constants.ParseMode.HTML
                        ))

            except Exception as e:
                logger.error(f"Ranking insertion error: {e}")

        return lines

def craft_profit_message(symbol, deposit, profit, percentage_gain, reason, trading_style, social_lines=None):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    multiplier = round(profit / deposit, 1)

    # If caller didn't pass lines, fetch (no live insert here)
    if social_lines is None:
        social_lines, _ = fetch_cached_rankings()

    social_text = "\n".join(social_lines)
    mention = random.choice(RANKING_TRADERS)[1]
    tag = "#MemeCoinGains #CryptoTrends" if symbol in MEME_COINS else "#StockMarket #CryptoWins"
    asset_desc = "Meme Coin" if symbol in MEME_COINS else symbol

    msg = (
        f"📈 <b>{symbol} Profit Update</b> 📈\n"
        f"<b>{trading_style}</b> on {asset_desc}\n"
        f"💰 Invested: ${deposit:,.2f}\n"
        f"🎯 {multiplier}x Return → Realized: ${profit:,.2f}\n"
        f"🔥 {reason}\n"
        f"📊 Achieved {percentage_gain}% ROI!\n"
        f"Time: {ts}\n\n"
        f"🏆 Top Trader Rankings:\n{social_text}\n"
        f"👉 Shoutout to {mention} for inspiring us!\n\n"
        f"Join us at Options Trading University for more insights! {tag}"
    )

    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return msg, reply_markup

def craft_success_story(current_index, gender):
    combined = [("male", s) for s in TRADER_STORIES["male"]] + [("female", s) for s in TRADER_STORIES["female"]]
    total = len(combined)
    current_index = current_index % total
    gender, story_data = combined[current_index]

    story = story_data["story"]
    image_url = story_data["image"]  # already a GitHub URL

    keyboard = [
        [InlineKeyboardButton("⬅️ Prev", callback_data=f"success_prev_{gender}_{current_index}")],
        [InlineKeyboardButton("➡️ Next", callback_data=f"success_next_{gender}_{current_index}")],
        [InlineKeyboardButton("Back to Menu", callback_data="back")]
    ]

    return story, InlineKeyboardMarkup(keyboard), image_url
def craft_trade_status():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    social_lines = fetch_cached_rankings()
    return (
        f"🏆 <b>Top Trader Rankings</b> 🏆\n"
        f"As of {ts}:\n"
        f"{'\n'.join(social_lines)}\n\n"
        f"Join the community at Options Trading University for more trading insights! #TradingCommunity"
    ), InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back")]])
# Log post content to DB and update user profits
def log_post(symbol, content, deposit, profit, user_id=None):
    try:
        with engine.begin() as conn:
            if user_id:
                conn.execute(
                    "UPDATE users SET total_profit = total_profit + :p WHERE user_id = :id",
                    {"p": profit, "id": user_id}
                )
            conn.execute(
                "INSERT INTO posts (symbol, content, deposit, profit, posted_at) VALUES (:s, :c, :d, :pr, :t)",
                {"s": symbol, "c": content, "d": deposit, "pr": profit, "t": datetime.now(timezone.utc)}
            )
    except Exception as e:
        logger.error(f"Database error: {e}")


# -------------------------
# Announce Winners (Daily, Weekly, Monthly)
# -------------------------
async def announce_winner(scope, app):
    """
    Announces the top winner for daily/weekly/monthly rankings.
    """
    lines = fetch_cached_rankings(scope)
    if not lines:
        return

    # Winner is always the first line in the leaderboard
    winner_line = lines[0]
    winner_name = winner_line.split("—")[0].split()[-1].strip("</b>")
    winner_profit = winner_line.split("—")[1].strip()

    msg = (
        f"🔥 <b>{scope.capitalize()} Winner!</b>\n"
        f"🏆 {winner_name} secured {winner_profit}!\n\n"
        f"Join the rankings at Options Trading University!"
    )

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=msg,
        parse_mode=constants.ParseMode.HTML
    )

# Background posting loop with mentions every 20 mins
# -------------------------
# Background posting loop with profit posts, rankings, and winner announcements
# -------------------------
async def profit_posting_loop(app):
    logger.info("Profit posting task started.")
    while True:
        try:
            # ⏳ Pick a realistic random interval (minutes)
            wait_minutes = random.choice([5, 10, 15, 20, 30, 40, 50, 60, 75, 90, 120])
            wait_seconds = wait_minutes * 60
            logger.info(f"Next profit post in {wait_minutes}m at {datetime.now(timezone.utc)}")
            await asyncio.sleep(wait_seconds)

            # 🔀 Pick symbol: 70% meme coins, 30% stocks/crypto
            if random.random() < 0.7:
                symbol = random.choice(MEME_COINS)
            else:
                symbol = random.choice([s for s in ALL_SYMBOLS if s not in MEME_COINS])
            
            # 🎯 Generate profit scenario
            deposit, profit, percentage_gain, reason, trading_style = generate_profit_scenario(symbol)
            msg, reply_markup = craft_profit_message(symbol, deposit, profit, percentage_gain, reason, trading_style)

            # ✅ Post to Telegram group
            try:
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=msg,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=reply_markup
                )
                logger.info(f"[PROFIT POSTED] {symbol} {trading_style} Deposit ${deposit:.2f} → Profit ${profit:.2f}")
                log_post(symbol, msg, deposit, profit)

                # 🆕 Pick a random trader name to try for leaderboard insertion
                trader_id, trader_name = random.choice(RANKING_TRADERS)
                fetch_cached_rankings(new_name=trader_name, new_profit=profit)

            except Exception as e:
                logger.error(f"Failed to post profit for {symbol}: {e}")

            await asyncio.sleep(RATE_LIMIT_SECONDS)

            # 📊 Occasionally also post rankings update (20% chance)
            if random.random() < 0.2:
                status_msg, status_reply_markup = craft_trade_status()
                try:
                    await app.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=status_msg,
                        parse_mode=constants.ParseMode.HTML,
                        reply_markup=status_reply_markup
                    )
                    logger.info("Posted trade status update.")
                    log_post(None, status_msg, None, None)
                except Exception as e:
                    logger.error(f"Failed to post trade status: {e}")

            # 🔔 Occasionally announce winners
            if random.random() < 0.05:   # 5% chance each cycle
                await announce_winner("daily", app)
            if random.random() < 0.02:   # ~2% chance each cycle
                await announce_winner("weekly", app)
            if random.random() < 0.01:   # ~1% chance each cycle
                await announce_winner("monthly", app)

        except asyncio.CancelledError:
            logger.info("Profit posting loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in posting loop: {e}")
            await asyncio.sleep(5)

# /start handler
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    name = user.first_name or user.username or "Trader"

    # Pick a random success story index
    total_stories = len(SUCCESS_STORY_TEMPLATES["male"]) + len(SUCCESS_STORY_TEMPLATES["female"])
    random_index = random.randint(0, total_stories - 1)

    keyboard = [
    [InlineKeyboardButton("View Rankings", callback_data="rankings"),
     InlineKeyboardButton("Success Stories", callback_data=f"success_any_{random_index}")],
    [InlineKeyboardButton("📢 Join Profit Group", url="https://t.me/+v2cZ4q1DXNdkMjI8")],
    [InlineKeyboardButton("Visit Website", url=WEBSITE_URL),
     InlineKeyboardButton("Terms of Service", callback_data="terms")],
    [InlineKeyboardButton("Privacy Policy", callback_data="privacy")]
]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"Welcome, {name}!\n\n"
        f"At Options Trading University, we provide expert-led training, real-time market analysis, "
        f"and a thriving community of successful traders. Our proven strategies have helped members achieve "
        f"consistent gains, with profit updates shared.\n"
        f"Why join us?\n"
        f"- Access to high-probability trades (up to 900% gains on meme coins).\n"
        f"- Guidance from top traders with a track record of success.\n"
        f"- Exclusive insights on stocks, crypto, and meme coins.\n\n"
        f"Start your journey to financial growth today!"
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=welcome_text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )

    try:
        with engine.begin() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username, display_name, wins, total_trades, total_profit) "
                "VALUES (:id, :u, :d, 0, 0, 0)",
                {"id": str(user.id), "u": user.username or "unknown", "d": name}
            )
    except Exception as e:
        logger.error(f"Error adding user {user.id}: {e}")# Callback handler for inline buttons
# Callback handler for inline buttons
# Callback handler for inline buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "rankings":
        status_msg, status_reply_markup = craft_trade_status()
        await query.edit_message_text(
            text=status_msg,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=status_reply_markup
        )

    elif data.startswith("success_"):
        parts = data.split("_")

        # success_any_3
        if parts[1] == "any":
            index = int(parts[2])
            gender = "any"

        # success_prev_male_3 or success_next_female_2
        elif parts[1] in ["prev", "next"]:
            action, gender, index = parts[1], parts[2], int(parts[3])
            index = index - 1 if action == "prev" else index + 1
        else:
            await query.edit_message_text("⚠️ Invalid success story request.")
            return

        # Get story
        story, reply_markup, image_url = craft_success_story(index, gender)

        if image_url and image_url.startswith("http"):
            from telegram import InputMediaPhoto
            try:
                await query.edit_message_media(
                    media=InputMediaPhoto(
                        media=image_url,
                        caption=f"📖 <b>Success Story</b>:\n{story}\n\nJoin Options Trading University to start your own journey!",
                        parse_mode=constants.ParseMode.HTML
                    ),
                    reply_markup=reply_markup
                )
            except Exception:
                # If edit fails (e.g. original was text), send new message
                await query.message.reply_photo(
                    photo=image_url,
                    caption=f"📖 <b>Success Story</b>:\n{story}\n\nJoin Options Trading University to start your own journey!",
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=reply_markup
                )
        else:
            await query.edit_message_text(
                text=f"📖 <b>Success Story</b>:\n{story}\n\nJoin Options Trading University to start your own journey!",
                parse_mode=constants.ParseMode.HTML,
                reply_markup=reply_markup
            )

    elif data == "terms":
        terms_text = (
            f"📜 <b>Terms of Service</b> 📜\n\n"
            f"1. Acceptance of Terms: By using this bot, you agree to abide by these Terms of Service.\n"
            f"2. User Conduct: Users must comply with all applicable laws and not use the bot for illegal activities.\n"
            f"3. Disclaimer: All trading insights are for informational purposes only and not financial advice.\n"
            f"4. Limitation of Liability: Options Trading University is not liable for any losses incurred.\n"
            f"5. Changes to Terms: We may update these terms at any time. Continued use constitutes acceptance.\n\n"
            f"For full terms, visit our website."
        )
        keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="back")]]
        await query.edit_message_text(
            text=terms_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "privacy":
        privacy_text = (
            f"🔒 <b>Privacy Policy</b> 🔒\n\n"
            f"1. Information Collected: We collect minimal data such as user IDs and usernames for bot functionality.\n"
            f"2. Use of Data: Data is used to personalize experiences and improve services.\n"
            f"3. Data Sharing: We do not sell your data. It may be shared with partners for service improvement.\n"
            f"4. Security: We use industry-standard measures to protect your data.\n"
            f"5. Changes to Policy: We may update this policy. Continued use constitutes acceptance.\n\n"
            f"For full privacy policy, visit our website."
        )
        keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="back")]]
        await query.edit_message_text(
            text=privacy_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "back":
        # 👇 Build the /start main menu again
        total_stories = len(TRADER_STORIES["male"]) + len(TRADER_STORIES["female"])
        random_index = random.randint(0, total_stories - 1)

        keyboard = [
            [InlineKeyboardButton("View Rankings", callback_data="rankings"),
             InlineKeyboardButton("Success Stories", callback_data=f"success_any_{random_index}")],
            [InlineKeyboardButton("Visit Website", url=WEBSITE_URL),
             InlineKeyboardButton("Terms of Service", callback_data="terms")],
            [InlineKeyboardButton("Privacy Policy", callback_data="privacy")]
        ]

        welcome_text = (
            f"📌 OPTIONS TRADING\n\n"
            f"At Options Trading University, we provide expert-led training, real-time market analysis, "
            f"and a thriving community of successful traders.\n\n"
            f"Why join us?\n"
            f"- Access to high-probability trades (up to 900% gains on meme coins).\n"
            f"- Guidance from top traders with a track record of success.\n"
            f"- Exclusive insights on stocks, crypto, and meme coins.\n\n"
            f"Start your journey to financial growth today!"
        )

        # Always send fresh new message so it works after photos/captions
        await query.message.reply_text(
            text=welcome_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
# /status handler
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📈 <b>Market Overview</b> 📊\n"
        f"Stocks: {', '.join(STOCK_SYMBOLS)}\n"
        f"Crypto: {', '.join(CRYPTO_SYMBOLS)}\n"
        f"Meme Coins: {', '.join(MEME_COINS)}\n"
        f"Profit updates drop every 20-40 minutes with gains up to 900%!\n\n"
        f"Join the action at Options Trading University! #TradingCommunity"
    )
    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )

# /help handler
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"ℹ️ <b>Help & Commands</b> ℹ️\n"
        f"/start - Welcome message and community link\n"
        f"/status - View current market focus\n"
        f"/trade_status - Check top trader rankings\n"
        f"/help - Display this help menu\n\n"
        f"Profit updates auto-post every 20-40 minutes. Join us at Options Trading University! #TradingSuccess"
    )
    keyboard = [
        [InlineKeyboardButton("View Rankings", callback_data="rankings"),
         InlineKeyboardButton("Visit Website", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )

# /trade_status handler
async def trade_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, reply_markup = craft_trade_status()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=reply_markup
    )

def main():
    if TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None:
        raise SystemExit("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in .env")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("trade_status", trade_status_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    async def on_startup(app):
        app.create_task(profit_posting_loop(app))
        logger.info("Profit posting task scheduled on startup.")

    app.post_init = on_startup

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
