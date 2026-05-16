# init_db.py
import sqlite3
from datetime import datetime

print("🚀 Initializing ASX O'Neil Database v3 (with RS table)...")

conn = sqlite3.connect('ASX_history.db')
cur = conn.cursor()

# Company List
cur.execute("""
    CREATE TABLE IF NOT EXISTS company_list (
        "Ticker" TEXT PRIMARY KEY,
        "ASX code" TEXT,
        "Company" TEXT,
        "Industry_Group" TEXT,
        "Market Cap" TEXT,
        "Market Cap Num" INTEGER,
        listing_date TEXT,
        updated_date TEXT,
        is_active INTEGER DEFAULT 1
    )
""")

# Price History
cur.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        date TEXT,
        ticker TEXT,
        close REAL,
        PRIMARY KEY (date, ticker)
    )
""")

# O'Neil RS Daily Table (this is what you asked for)
cur.execute("""
    CREATE TABLE IF NOT EXISTS oneil_rs (
        date TEXT,
        ticker TEXT,
        rs_value REAL,
        rs_rank REAL,
        rs_rating INTEGER,
        PRIMARY KEY (date, ticker)
    )
""")

# Indexes for speed
cur.execute("CREATE INDEX IF NOT EXISTS idx_price_ticker ON price_history(ticker)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_rs_date ON oneil_rs(date)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_rs_ticker ON oneil_rs(ticker)")

print("✅ Database tables ready:")
print("   • company_list")
print("   • price_history")
print("   • oneil_rs (daily O'Neil RS - 1 year history)")

conn.commit()
conn.close()
print(f"🎉 Database initialized at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")