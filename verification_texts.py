# verification_texts.py
# ✅ Auto-generated: works with Profit Flex Bot (uses main DB engine)
# ✅ Handles TXID uniqueness + category-specific verification lines
# ✅ No circular imports (expects `engine` passed in externally)

import random
import uuid
from datetime import datetime
from sqlalchemy import Table, Column, String, DateTime, MetaData, select, insert, update

# ====== Import text pools ======
from stock_verification import STOCK_VERIFICATIONS, CRYPTO_VERIFICATIONS, MEME_VERIFICATIONS


# --- Runtime TXID table (created in main if not existing) ---
metadata = MetaData()
txids = Table(
    "txids", metadata,
    Column("txid", String, primary_key=True),
    Column("used_at", DateTime)
)

# --- TXID generation with DB connection passed from main ---
def generate_unique_txid(engine):
    """Generate unique TXID and store it in DB (avoiding repeats)."""
    now = datetime.utcnow()
    with engine.begin() as conn:
        metadata.create_all(engine)  # ensure table exists
        # clean up older than 48h
        conn.execute(
            txids.delete().where(
                txids.c.used_at < datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            )
        )

        # Try new random TXIDs
        for _ in range(100):
            txid = uuid.uuid4().hex[:8].upper()
            exists = conn.execute(select(txids.c.txid).where(txids.c.txid == txid)).scalar()
            if not exists:
                conn.execute(insert(txids).values(txid=txid, used_at=now))
                return f"TX#{txid}"

        # fallback to reuse oldest
        oldest = conn.execute(select(txids.c.txid).order_by(txids.c.used_at.asc()).limit(1)).scalar()
        if oldest:
            conn.execute(update(txids).where(txids.c.txid == oldest).values(used_at=now))
            return f"TX#{oldest}"

        # last resort: generate new
        txid = uuid.uuid4().hex[:8].upper()
        conn.execute(insert(txids).values(txid=txid, used_at=now))
        return f"TX#{txid}"


# --- Main verification text picker ---
def get_random_verification(symbol: str, engine=None) -> str:
    """
    Pick a random verification line based on the symbol.
    Auto-selects stock / crypto / meme pool.
    Uses TXIDs stored via the shared DB engine.
    """
    symbol = symbol.upper().strip()
    txid = generate_unique_txid(engine) if engine else f"TX#{uuid.uuid4().hex[:8].upper()}"

    stock_tags = {"AAPL","MSFT","NVDA","TSLA","AMZN","META","GOOGL","SPY","QQQ","NFLX","AMD"}
    crypto_tags = {"BTC","ETH","SOL","BNB","XRP","ADA","DOGE","SHIB","AVAX","DOT","MATIC"}
    meme_tags   = {"NIKY","PEPE","BONK","WIF","SAMO","POPCAT","HOSKY","PONKE","COQ"}

    if symbol in stock_tags:
        pool = STOCK_VERIFICATIONS
    elif symbol in crypto_tags:
        pool = CRYPTO_VERIFICATIONS
    elif symbol in meme_tags:
        pool = MEME_VERIFICATIONS
    else:
        pool = STOCK_VERIFICATIONS + CRYPTO_VERIFICATIONS + MEME_VERIFICATIONS

    line = random.choice(pool)
    return line.format(txid=txid)
