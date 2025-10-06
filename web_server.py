import os
import logging
from flask import Flask, render_template, jsonify
from sqlalchemy import select, text   # ✅ Added text import
from dotenv import load_dotenv
from datetime import datetime, timezone  # ✅ Added datetime import

# Try to import database models
try:
    from models import engine, trade_logs
except Exception as e:
    logging.critical(f"Failed to import from models.py: {e}")
    raise

# --- Configure logging globally ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)  # ✅ Define logger properly

logging.info("Web server script starting up...")

# --- Load environment ---
load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    """Health check route."""
    logger.info("Root URL '/' was hit successfully.")
    return "✅ Web Server is running and accessible."

# ✅ /api/recent — returns JSON of last 40 trades
@app.route("/api/recent")
def recent_trade_logs():
    """Return up to 40 most recent trades as JSON."""
    try:
        with engine.connect() as conn:
            query = """
                SELECT txid, symbol, trader_name,
                       COALESCE(broker_name, 'Verified Exchange') AS broker_name,
                       profit, roi, posted_at
                FROM trade_logs
                ORDER BY posted_at DESC
                LIMIT 40
            """
            rows = conn.execute(text(query)).mappings().all()

        if not rows:
            return jsonify({"message": "No recent trades found."}), 200

        data = []
        for row in rows:
            data.append({
                "txid": row["txid"],
                "symbol": row["symbol"],
                "broker_name": row["broker_name"],
                "trader_name": row["trader_name"],
                "profit": float(row["profit"] or 0),
                "roi": float(row["roi"] or 0),
                "posted_at": (
                    row["posted_at"].isoformat()
                    if row["posted_at"]
                    else datetime.now(timezone.utc).isoformat()
                ),
            })

        return jsonify(data), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"⚠️ Error fetching /api/recent: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ /log/<txid> — individual trade viewer
@app.route('/log/<txid>')
def show_log(txid):
    """Display verification details for a specific trade."""
    logger.info(f"Log for txid '{txid}' was requested.")
    try:
        with engine.connect() as conn:
            stmt = select(trade_logs).where(trade_logs.c.txid == txid)
            result = conn.execute(stmt).fetchone()
        
        if not result:
            logger.warning(f"TXID '{txid}' not found in the database.")
            return (
                "<h2>⚠️ Trade Snapshot Not Found</h2>"
                "<p>This transaction ID may have expired or hasn't been posted yet.</p>"
                "<p><a href='/'>Return Home</a></p>",
                404,
            )
        
        trade_data = dict(result._mapping)
        return render_template('log_template.html', trade=trade_data)
    
    except Exception as e:
        logger.error(f"Error while fetching log for {txid}: {e}", exc_info=True)
        return (
            "<h2>500 - Internal Server Error</h2>"
            "<p>An error occurred. Please check logs for details.</p>"
            "<p><a href='/'>Return Home</a></p>",
            500,
        )

# ✅ Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return "<h1>500 - Internal Server Error</h1><p>An error occurred. Please check the application logs for details.</p>", 500

logger.info("Web server setup is complete. Gunicorn will now manage the application.")
