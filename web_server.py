import os
import logging
from flask import Flask, render_template, abort
from sqlalchemy import select
from dotenv import load_dotenv

# Try to import the database models
try:
    from models import engine, trade_logs
except Exception as e:
    # This will log the error if the models file has an issue
    logging.critical(f"Failed to import from models.py: {e}")
    raise

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("Web server script starting up...")

# Load environment variables
load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    """A simple route to confirm the web server is running and for health checks."""
    logging.info("Root URL '/' was hit successfully.")
    return "✅ Web Server is running and accessible."

@app.route('/log/<txid>')
def show_log(txid):
    """Fetches and displays a specific trade log."""
    logging.info(f"Log for txid '{txid}' was requested.")
    try:
        with engine.connect() as conn:
            stmt = select(trade_logs).where(trade_logs.c.txid == txid)
            result = conn.execute(stmt).fetchone()
        
        if not result:
            logging.warning(f"TXID '{txid}' not found in the database.")
            abort(404)
        
        trade_data = dict(result._mapping)
        return render_template('log_template.html', trade=trade_data)
    
    except Exception as e:
        logging.error(f"A server error occurred while fetching log for {txid}: {e}", exc_info=True)
        abort(500)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return "<h1>500 - Internal Server Error</h1><p>An error occurred. Please check the application logs for details.</p>", 500

logging.info("Web server setup is complete. Gunicorn will now manage the application.")
