# web_server.py

import os
from flask import Flask, render_template, abort
from sqlalchemy import select
from dotenv import load_dotenv

# ✅ CORRECT: We now import everything needed from models.py
from models import engine, trade_logs

# Load environment variables
load_dotenv()

app = Flask(__name__)

@app.route('/log/<txid>')
def show_log(txid):
    """
    Fetches trade data by its TXID and renders it in an HTML template.
    """
    # This now uses the correctly imported 'engine' and 'trade_logs'
    with engine.connect() as conn:
        stmt = select(trade_logs).where(trade_logs.c.txid == txid)
        result = conn.execute(stmt).fetchone()

    if not result:
        abort(404)

    trade_data = dict(result._mapping)
    return render_template('log_template.html', trade=trade_data)

@app.errorhandler(404)
def page_not_found(e):
    # Custom 404 page
    return render_template('404.html'), 404

@app.route('/')
def home():
    return "✅ Stockbot Web Server is Live — use /log/<TXID> to view trade logs."
@app.route('/health')
def health():
    return "ok", 200
