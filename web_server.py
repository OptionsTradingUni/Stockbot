# web_server.py

import os
from flask import Flask, render_template, abort
from models import engine, trade_logs
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment.")

engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Attempt to reflect the tables from the database
try:
    metadata.reflect(bind=engine)
    trade_logs = metadata.tables['trade_logs']
except KeyError:
    print("FATAL: 'trade_logs' table not found. Make sure the bot has run once to create it.")
    exit(1)
except Exception as e:
    print(f"FATAL: Could not connect to the database or reflect tables: {e}")
    exit(1)


@app.route('/log/<txid>')
def show_log(txid):
    """
    Fetches trade data by its TXID and renders it in an HTML template.
    """
    with engine.connect() as conn:
        stmt = select(trade_logs).where(trade_logs.c.txid == txid)
        result = conn.execute(stmt).fetchone()

    if not result:
        # If no trade log is found, show a 404 error page
        abort(404)

    # Convert the database row into a more usable dictionary format
    trade_data = dict(result._mapping)
    return render_template('log_template.html', trade=trade_data)

@app.errorhandler(404)
def page_not_found(e):
    # Custom 404 page
    return render_template('404.html'), 404

# To run this server, use the command: gunicorn web_server:app
