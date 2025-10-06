import os
from flask import Flask, render_template, abort
from sqlalchemy import select
from dotenv import load_dotenv
from models import engine, trade_logs

# Load environment variables
load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    """
    Root route for Railway health check and visitors.
    """
    return (
        "<h2 style='font-family:sans-serif;color:#16f;'>✅ Stockbot Web Server is Live</h2>"
        "<p>Use <code>/log/&lt;TXID&gt;</code> to view individual trade logs.</p>"
        "<p>Example: <a href='/log/DEMO1234'>/log/DEMO1234</a></p>"
    )

@app.route('/log/<txid>')
def show_log(txid):
    """
    Fetch trade data from the database and render the verification log.
    """
    try:
        with engine.connect() as conn:
            stmt = select(trade_logs).where(trade_logs.c.txid == txid)
            result = conn.execute(stmt).fetchone()

        if not result:
            abort(404)

        trade_data = dict(result._mapping)
        return render_template('log_template.html', trade=trade_data)

    except Exception as e:
        # Render 404-style error but with reason
        return (
            f"<h3 style='color:red;font-family:sans-serif;'>Server Error</h3>"
            f"<p>{e}</p>",
            500
        )

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
