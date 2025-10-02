import os
from dotenv import load_dotenv

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

# posting interval weights (minutes)
POST_MINUTES = [5, 10, 15, 20, 30, 60, 120]
POST_WEIGHTS = [0.25, 0.25, 0.22, 0.18, 0.06, 0.03, 0.01]

# cache TTL
RANKINGS_TTL_HOURS = 5
