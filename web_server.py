# web_server.py
from flask import Flask, render_template, abort
import os
from datetime import datetime
import random

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ StockBot Flask server is running and responding!"

@app.route('/log/<txid>')
def show_log(txid):
    trade = {
        "txid": txid,
        "symbol": "AAPL",
        "broker_name": "Interactive Brokers",
        "timestamp": datetime.utcnow(),
        "direction": "Buy",
        "quantity": 10,
        "entry_price": 193.5,
        "exit_price": 205.7,
        "deposit": 1935.0,
        "total_value_exit": 2057.0,
        "commission": 1.25,
        "profit": 122.0,
        "slippage": 0.04,
        "status": "Filled",
        "trader_name": "Alexander Kowalski"
    }
    return render_template("log_template.html", trade=trade)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Railway injects PORT
    app.run(host="0.0.0.0", port=port, debug=False)
