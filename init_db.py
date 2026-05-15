# init_db.py
import sqlite3
from datetime import datetime

print("🚀 Initializing clean ASX O'Neil Database (v2 - full schema)...")

conn = sqlite3.connect('ASX_history.db')
cur = conn.cursor()

# === 1. Company List Table ===
cur.execute("""
    CREATE TABLE IF NOT EXISTS company_list (
        ticker TEXT PRIMARY KEY,
        name TEXT,
        sector TEXT,
        industry TEXT,
        market_cap REAL,
        status TEXT,
        listing_date TEXT,
        updated_date TEXT
    )
""")

# === 2. Price History Table (full OHLCV) ===
cur.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        date TEXT,
        ticker TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY (date, ticker)
    )
""")

# Indexes for speed
cur.execute("CREATE INDEX IF NOT EXISTS idx_price_ticker ON price_history(ticker)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_price_date ON price_history(date)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_price_ticker_date ON price_history(ticker, date)")

print("✅ Tables created: company_list + price_history (full OHLCV)")

conn.commit()
conn.close()

print(f"✅ Database initialized successfully → ASX_history.db")
print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")