# verification_texts.py
import random
import uuid
import re
from datetime import datetime, timedelta
from sqlalchemy import Table, Column, String, DateTime, MetaData, select, insert, delete, update

# Import text pools from the separate file
from stock_verification import STOCK_VERIFICATIONS, CRYPTO_VERIFICATIONS, MEME_VERIFICATIONS

# --- Runtime TXID table definition ---
metadata = MetaData()
txids = Table(
    "txids", metadata,
    Column("txid", String, primary_key=True),
    Column("used_at", DateTime)
)

# --- TXID Generation ---
def generate_unique_txid(engine):
    """
    Generates a unique 8-character TXID, stores it in the DB, and prunes old ones.
    Returns the raw TXID (e.g., 'A1B2C3D4').
    """
    now = datetime.utcnow()
    with engine.begin() as conn:
        metadata.create_all(conn, checkfirst=True)  # Ensure table exists
        
        # Prune TXIDs older than 72 hours
        conn.execute(delete(txids).where(txids.c.used_at < now - timedelta(hours=72)))

        for _ in range(100):
            txid = uuid.uuid4().hex[:8].upper()
            exists = conn.execute(select(txids).where(txids.c.txid == txid)).first()
            if not exists:
                conn.execute(insert(txids).values(txid=txid, used_at=now))
                return txid
        
        # Fallback: just generate one, collision is astronomically unlikely
        txid = uuid.uuid4().hex[:8].upper()
        conn.execute(insert(txids).values(txid=txid, used_at=now))
        return txid

# --- Broker Name Parsing ---
def _extract_broker_name(text: str) -> str:
    """
    Extracts the broker/platform name from a verification string.
    """
    # This regex looks for patterns like "through [Name] brokerage", "through [Name] explorer", etc.
    patterns = [
        r"through ([\w\s\.\*\'\d]+?)\s(?:broker|log|feed|ledger|history|report|record|export|explorer|wallet|analytics|feed)",
        r"through (Uniswap v3|Jupiter aggregator)",
        r"on (E\*TRADE|OKX)" # Special cases
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Clean up the name
            name = match.group(1).strip()
            if name.lower().endswith(" brokerage"):
                name = name[:-10]
            return name.title() # e.g., "Charles Schwab"
            
    return "Verified Exchange" # Default fallback

# --- Main Verification Text Picker ---
def get_random_verification(symbol: str, txid: str, engine) -> tuple[str, str]:
    """
    Picks a random verification line based on the symbol and returns both the
    formatted text and the parsed broker name.
    """
    symbol = symbol.upper().strip()

    stock_tags = {"AAPL","MSFT","NVDA","TSLA","AMZN","META","GOOGL"}
    crypto_tags = {"BTC","ETH","SOL"}
    meme_tags   = {"NIKY"}

    if symbol in stock_tags:
        pool = STOCK_VERIFICATIONS
    elif symbol in crypto_tags:
        pool = CRYPTO_VERIFICATIONS
    elif symbol in meme_tags:
        pool = MEME_VERIFICATIONS
    else: # Fallback for any other symbols
        pool = STOCK_VERIFICATIONS + CRYPTO_VERIFICATIONS 

    # Choose a random line from the pool
    line = random.choice(pool)
    
    # Extract broker name BEFORE formatting
    broker_name = _extract_broker_name(line)
    
    # Format the line with the TXID
    formatted_line = line.format(txid=f"TX#{txid}")
    
    return formatted_line, broker_name
