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
# Countries & Traders
# -----------------------

# Define countries
COUNTRIES = ["USA", "Nigeria", "UK", "Japan", "India", "Germany", "France", "Brazil"]

# Assign traders by country (so no mismatch)
RANKING_TRADERS = {
    "USA": [
        ("RobertGarcia", "Robert Garcia"),
        ("JamesLopez", "James Lopez"),
        ("MichaelBrown", "Michael Brown"),
        ("WilliamRodriguez", "William Rodriguez"),
        ("ThomasClark", "Thomas Clark"),
    ],
    "Nigeria": [
        ("ChineduOkafor", "Chinedu Okafor"),
        ("NgoziBalogun", "Ngozi Balogun"),
        ("TundeAdebayo", "Tunde Adebayo"),
        ("FunmiOlawale", "Funmi Olawale"),
        ("BenjaminScott", "Benjamin Scott"),
    ],
    "UK": [
        ("CharlotteTorres", "Charlotte Torres"),
        ("EllaWright", "Ella Wright"),
        ("HenryAllen", "Henry Allen"),
        ("VictoriaHarris", "Victoria Harris"),
        ("JosephTurner", "Joseph Turner"),
    ],
    "India": [
        ("RaviPatel", "Ravi Patel"),
        ("PriyaSharma", "Priya Sharma"),
        ("AmitKumar", "Amit Kumar"),
        ("NehaVerma", "Neha Verma"),
        ("SanjaySingh", "Sanjay Singh"),
    ],
    "Germany": [
        ("HansMuller", "Hans Muller"),
        ("KlaraSchmidt", "Klara Schmidt"),
        ("FritzBecker", "Fritz Becker"),
        ("SophieFischer", "Sophie Fischer"),
        ("LukasWagner", "Lukas Wagner"),
    ],
    "France": [
        ("PierreDubois", "Pierre Dubois"),
        ("MarieClaire", "Marie Claire"),
        ("JulienLefevre", "Julien Lefevre"),
        ("CamilleRoux", "Camille Roux"),
        ("AntoineGirard", "Antoine Girard"),
    ],
    "Japan": [
        ("HiroshiTanaka", "Hiroshi Tanaka"),
        ("YukiSato", "Yuki Sato"),
        ("KenjiYamamoto", "Kenji Yamamoto"),
        ("AyaNakamura", "Aya Nakamura"),
        ("TaroKobayashi", "Taro Kobayashi"),
    ],
    "Brazil": [
        ("CarlosSilva", "Carlos Silva"),
        ("AnaCosta", "Ana Costa"),
        ("JoaoSouza", "Joao Souza"),
        ("MariaOliveira", "Maria Oliveira"),
        ("PauloSantos", "Paulo Santos"),
    ]
}

# Flatten list for use in leaderboards
ALL_TRADERS = [(tid, name) for country in RANKING_TRADERS.values() for tid, name in country]

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
