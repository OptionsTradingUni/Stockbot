import os
import logging
from flask import Flask, render_template, jsonify
from flask_cors import CORS  # <-- ADD THIS IMPORT
from sqlalchemy import select, text
from dotenv import load_dotenv
from datetime import datetime, timezone

# --- Configure logging globally ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.info("Web server script starting up...")

# --- Load environment ---
load_dotenv()

# --- Import database models safely ---
try:
    from models import engine, trade_logs
except Exception as e:
    logger.critical(f"Failed to import from models.py: {e}")
    raise

# --- Flask app setup ---
app = Flask(__name__)
CORS(app)  # <-- ADD THIS RIGHT AFTER CREATING THE APP

@app.route("/")
def home():
    """Basic health check route."""
    logger.info("Root URL '/' accessed successfully.")
    return "✅ Web Server is running and accessible."

# ----------------------------------------------------------------------
# API route to provide the last 100 trades as raw data
# ----------------------------------------------------------------------
@app.route("/api/recent100")
def api_recent_100():
    """Return up to 100 most recent trades as JSON data."""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT txid, symbol, trader_name, profit, roi, posted_at
                FROM trade_logs ORDER BY posted_at DESC LIMIT 100
            """)
            rows = conn.execute(query).mappings().all()

        data = []
        for row in rows:
            posted_at = row.get("posted_at")
            data.append({
                "txid": row["txid"],  # <-- ✅ THIS LINE IS THE FIX
                "symbol": row["symbol"],
                "trader_name": row["trader_name"],
                "profit": float(row["profit"] or 0),
                "roi": float(row["roi"] or 0),
                "time_ago": time_ago(posted_at) if posted_at else "Unknown time"
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": "Failed to fetch trades"}), 500
        
# ----------------------------------------------------------------------
# Helper: Time-ago formatting
# ----------------------------------------------------------------------
def time_ago(posted_at):
    """Convert datetime into 'x time ago' string."""
    if not posted_at:
        return "Unknown time"
    now = datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    diff = now - posted_at
    seconds = diff.total_seconds()
    minutes = int(seconds // 60)
    hours = int(minutes // 60)
    days = int(hours // 24)
    if seconds < 60:
        return "just now"
    elif minutes < 60:
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif hours < 24:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        return f"{days} day{'s' if days > 1 else ''} ago"

# ----------------------------------------------------------------------
# /api/recent — JSON API for last 40 trades
# ----------------------------------------------------------------------
@app.route("/api/recent")
def recent_trade_logs():
    """Return up to 40 most recent trades as JSON."""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT txid, symbol, trader_name,
                       COALESCE(broker_name, 'Verified Exchange') AS broker_name,
                       profit, roi, posted_at
                FROM trade_logs
                ORDER BY posted_at DESC
                LIMIT 40
            """)
            rows = conn.execute(query).mappings().all()

        if not rows:
            return jsonify({"message": "No recent trades found."}), 200

        data = []
        for row in rows:
            posted_at = row.get("posted_at")
            data.append({
                "txid": row["txid"],
                "symbol": row["symbol"],
                "broker_name": row["broker_name"],
                "trader_name": row["trader_name"],
                "profit": float(row["profit"] or 0),
                "roi": float(row["roi"] or 0),
                "posted_at": posted_at.isoformat() if posted_at else None,
                "time_ago": time_ago(posted_at) if posted_at else "Unknown time"
            })

        return jsonify(data), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"⚠️ Error fetching /api/recent: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# ----------------------------------------------------------------------
# /log/<txid> — Single Trade Viewer
# ----------------------------------------------------------------------
@app.route("/log/<txid>")
def show_log(txid):
    """Display verification details for a specific trade."""
    logger.info(f"Log for txid '{txid}' requested.")
    try:
        with engine.connect() as conn:
            stmt = select(trade_logs).where(trade_logs.c.txid == txid)
            result = conn.execute(stmt).fetchone()

        if not result:
            logger.warning(f"TXID '{txid}' not found in database.")
            return (
                "<h2>⚠️ Trade Snapshot Not Found</h2>"
                "<p>This transaction ID may have expired or hasn't been posted yet.</p>"
                "<p><a href='/'>Return Home</a></p>",
                404,
            )

        trade_data = dict(result._mapping)
        trade_data["time_ago"] = time_ago(trade_data.get("posted_at"))
        return render_template("log_template.html", log=trade_data)

    except Exception as e:
        logger.error(f"Error while fetching log for {txid}: {e}", exc_info=True)
        return (
            "<h2>500 - Internal Server Error</h2>"
            "<p>An error occurred. Please check logs for details.</p>"
            "<p><a href='/'>Return Home</a></p>",
            500,
        )

# ----------------------------------------------------------------------
# Error handlers
# ----------------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return (
        "<h1>500 - Internal Server Error</h1>"
        "<p>An error occurred. Please check the application logs for details.</p>",
        500,
    )

logger.info("✅ Web server setup complete — ready for Gunicorn or Flask run.")
