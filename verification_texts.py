# Auto-generated verification_texts.py
import random
import uuid
from datetime import datetime
from sqlalchemy import select, insert, update
from profit_flex_bot import engine  # Assuming main has the engine
from stock_verification import STOCK_VERIFICATIONS, CRYPTO_VERIFICATIONS, MEME_VERIFICATIONS
# Table for tracking used TXIDs
from sqlalchemy import Table, Column, String, DateTime, MetaData
metadata = MetaData()
txids = Table(
    "txids", metadata,
    Column("txid", String, primary_key=True),
    Column("used_at", DateTime)
)

# Create table if not exists
metadata.create_all(engine)


def generate_unique_txid():
    """Generate a unique 8-character uppercase hex TXID and store it in the database."""
    ttl_seconds = 24 * 60 * 60  # 24-hour cooldown for TXID reuse
    now = datetime.now().timestamp()

    # Prune old TXIDs
    with engine.connect() as conn:
        old_txids = conn.execute(
            select(txids.c.txid).where(
                (datetime.now() - txids.c.used_at) > ttl_seconds
            )
        ).scalars().all()
        for txid in old_txids:
            conn.execute(txids.delete().where(txids.c.txid == txid))
        conn.commit()

    # Generate new TXID
    for _ in range(100):  # Try up to 100 times
        txid = uuid.uuid4().hex[:8].upper()  # 8-character uppercase hex
        with engine.connect() as conn:
            exists = conn.execute(
                select(txids.c.txid).where(txids.c.txid == txid)
            ).scalar()
            if not exists:
                conn.execute(
                    insert(txids).values(
                        txid=txid,
                        used_at=datetime.now()
                    )
                )
                conn.commit()
                return txid

    # Fallback: reuse oldest TXID if no unique one found
    with engine.connect() as conn:
        oldest = conn.execute(
            select(txids.c.txid).order_by(txids.c.used_at.asc()).limit(1)
        ).scalar()
        if oldest:
            conn.execute(
                update(txids).where(txids.c.txid == oldest).values(
                    used_at=datetime.now()
                )
            )
            conn.commit()
            return oldest
        # Last resort: generate new and force insert
        txid = uuid.uuid4().hex[:8].upper()
        conn.execute(
            insert(txids).values(
                txid=txid,
                used_at=datetime.now()
            )
        )
        conn.commit()
        return txid

def random_verification_line(symbol: str = "", stock_symbols=None, crypto_symbols=None, meme_coins=None):
    s = symbol.upper().strip()
    stock_symbols = [x.upper() for x in (stock_symbols or [])]
    crypto_symbols = [x.upper() for x in (crypto_symbols or [])]
    meme_coins = [x.upper() for x in (meme_coins or [])]
    if s in meme_coins: pool = MEME_VERIFICATIONS
    elif s in crypto_symbols: pool = CRYPTO_VERIFICATIONS
    elif s in stock_symbols: pool = STOCK_VERIFICATIONS
    else: pool = STOCK_VERIFICATIONS + CRYPTO_VERIFICATIONS + MEME_VERIFICATIONS
    line = random.choice(pool)
    txid = generate_unique_txid()
    return line.format(txid=f"TX#{txid}")
