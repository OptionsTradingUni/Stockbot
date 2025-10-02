import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

# -----------------------
# Environment Variables
# -----------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STOCK_SYMBOLS = ["TSLA", "AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META"]
CRYPTO_SYMBOLS = ["BTC", "ETH", "SOL"]
MEME_COINS = ["NIKY"]
ALL_SYMBOLS = STOCK_SYMBOLS + CRYPTO_SYMBOLS + MEME_COINS

WEBSITE_URL = "https://optionstradinguni.online/"

# -----------------------
# data.py

# 🌍 Supported countries
COUNTRIES = ["USA", "Nigeria", "UK", "India", "Germany"]

# 🌍 Global trader list (id, display name)
RANKING_TRADERS = [
    # USA
    ("JamesLopez", "James Lopez"),
    ("RobertGarcia", "Robert Garcia"),
    ("SophiaGonzalez", "Sophia Gonzalez"),
    ("WilliamRodriguez", "William Rodriguez"),
    ("OliviaHernandez", "Olivia Hernandez"),
    ("MichaelBrown", "Michael Brown"),
    ("DavidMiller", "David Miller"),
    ("EmmaWhite", "Emma White"),
    ("JosephTurner", "Joseph Turner"),
    ("GraceAdams", "Grace Adams"),

    # Nigeria
    ("BenjaminScott", "Benjamin Scott"),
    ("ChineduOkafor", "Chinedu Okafor"),
    ("NgoziAdeyemi", "Ngozi Adeyemi"),
    ("TundeBalogun", "Tunde Balogun"),
    ("AmakaObi", "Amaka Obi"),
    ("IbrahimLawal", "Ibrahim Lawal"),
    ("FunkeOlawale", "Funke Olawale"),
    ("VictorUche", "Victor Uche"),
    ("AishaBello", "Aisha Bello"),
    ("SamuelOkon", "Samuel Okon"),

    # UK
    ("CharlotteTorres", "Charlotte Torres"),
    ("EllaWright", "Ella Wright"),
    ("HenryAllen", "Henry Allen"),
    ("ThomasClark", "Thomas Clark"),
    ("DanielKing", "Daniel King"),
    ("RebeccaMoore", "Rebecca Moore"),
    ("OliverHughes", "Oliver Hughes"),
    ("GeorgeHill", "George Hill"),
    ("AmeliaScott", "Amelia Scott"),
    ("ChloeYoung", "Chloe Young"),

    # India
    ("RaviKumar", "Ravi Kumar"),
    ("PriyaSharma", "Priya Sharma"),
    ("ArjunPatel", "Arjun Patel"),
    ("AnanyaGupta", "Ananya Gupta"),
    ("RohitVerma", "Rohit Verma"),
    ("SanjaySingh", "Sanjay Singh"),
    ("MeeraIyer", "Meera Iyer"),
    ("VikramJoshi", "Vikram Joshi"),
    ("SnehaReddy", "Sneha Reddy"),
    ("KiranNair", "Kiran Nair"),

    # Germany
    ("LukasMeyer", "Lukas Meyer"),
    ("HannahSchmidt", "Hannah Schmidt"),
    ("JonasFischer", "Jonas Fischer"),
    ("LeaWeber", "Lea Weber"),
    ("FelixBecker", "Felix Becker"),
    ("SophieWagner", "Sophie Wagner"),
    ("MaxSchneider", "Max Schneider"),
    ("MiaKoch", "Mia Koch"),
    ("PaulNeumann", "Paul Neumann"),
    ("ClaraHoffmann", "Clara Hoffmann"),
]

# 🌍 Country-to-trader mapping
COUNTRY_TRADERS = {
    "USA": [
        "JamesLopez", "RobertGarcia", "SophiaGonzalez", "WilliamRodriguez",
        "OliviaHernandez", "MichaelBrown", "DavidMiller", "EmmaWhite",
        "JosephTurner", "GraceAdams"
    ],
    "Nigeria": [
        "BenjaminScott", "ChineduOkafor", "NgoziAdeyemi", "TundeBalogun",
        "AmakaObi", "IbrahimLawal", "FunkeOlawale", "VictorUche",
        "AishaBello", "SamuelOkon"
    ],
    "UK": [
        "CharlotteTorres", "EllaWright", "HenryAllen", "ThomasClark",
        "DanielKing", "RebeccaMoore", "OliverHughes", "GeorgeHill",
        "AmeliaScott", "ChloeYoung"
    ],
    "India": [
        "RaviKumar", "PriyaSharma", "ArjunPatel", "AnanyaGupta",
        "RohitVerma", "SanjaySingh", "MeeraIyer", "VikramJoshi",
        "SnehaReddy", "KiranNair"
    ],
    "Germany": [
        "LukasMeyer", "HannahSchmidt", "JonasFischer", "LeaWeber",
        "FelixBecker", "SophieWagner", "MaxSchneider", "MiaKoch",
        "PaulNeumann", "ClaraHoffmann"
    ]
}

# 🌐 Website URL
WEBSITE_URL = "https://optionstradinguni.online/"

# Flattened list (all traders, still useful in leaderboards/rankings)
RANKING_TRADERS = [trader for country, traders in COUNTRY_TRADERS.items() for trader in traders]
SUCCESS_TRADERS = {
    "male": [
        ("JohnDoeTrader", "John Doe", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male1.jpeg"),
        ("AlexJohnson", "Alex Johnson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male2.jpeg"),
        ("MichaelBrown", "Michael Brown", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male3.jpeg"),
        ("DavidMiller", "David Miller", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male4.jpeg"),
        ("ChrisAnderson", "Chris Anderson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/male5.jpeg"),
    ],
    "female": [
        ("JaneSmithPro", "Jane Smith", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female1.jpeg"),
        ("EmilyDavis", "Emily Davis", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female2.jpeg"),
        ("SarahWilson", "Sarah Wilson", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female3.jpeg"),
        ("LauraTaylor", "Laura Taylor", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female4.jpeg"),
        ("AnnaMartinez", "Anna Martinez", "https://raw.githubusercontent.com/OptionsTradingUni/Stockbot/main/images/female5.jpeg"),
    ],
}

SUCCESS_STORY_TEMPLATES = {
    "male": [
        "transformed a modest ${deposit} investment into an impressive ${profit} through a meticulously planned swing trade on AAPL.",
        "turned ${deposit} into a remarkable ${profit} by mastering the art of BTC HODL.",
        "flipped a ${deposit} stake into ${profit} with a bold NIKY pump riding move.",
        "achieved a stunning ${profit} profit from a strategic ETH DCA plan starting with ${deposit}.",
        "earned ${profit} through a clever SOL arbitrage play after investing ${deposit}.",
    ],
    "female": [
        "grew a ${deposit} investment into ${profit} with a disciplined TSLA scalping strategy.",
        "boosted ${deposit} into ${profit} with an early sniping move on DOGE.",
        "turned ${deposit} into ${profit} via a SHIB community flip.",
        "made ${profit} from a NVDA position trade starting with ${deposit}.",
        "grew ${deposit} into ${profit} with a GOOGL day trading plan.",
    ],
}

NEWS_CATALYSTS = {
    "stocks": [
        "surged after strong earnings",
        "climbed on analyst upgrade",
        "rallied on new product launch",
        "gained on partnership news",
        "spiked with positive sentiment",
    ],
    "crypto": [
        "pumped after whale accumulation",
        "rose on adoption news",
        "surged on protocol upgrade",
        "gained after exchange listing",
        "spiked with DeFi integration",
    ],
    "meme_coins": [
        "mooned after viral tweet",
        "pumped on community hype",
        "surged with influencer shoutout",
        "rocketed after Reddit buzz",
        "spiked on meme-driven volume",
    ],
}
