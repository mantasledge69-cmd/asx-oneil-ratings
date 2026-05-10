import sqlite3
from datetime import datetime

DB_PATH = 'ASX_history.db'

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🚀 Initializing clean ASX O'Neil Database...")

    # Company List
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_list (
            Ticker           TEXT PRIMARY KEY,
            ASX_code         TEXT,
            Company          TEXT,
            Industry_Group   TEXT,
            "Market Cap"     TEXT,
            "Market Cap Num" REAL,
            listing_date     TEXT,
            updated_date     TEXT,
            is_active        INTEGER DEFAULT 1
        )
    ''')

    # Price History - Minimal
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            date    TEXT NOT NULL,
            ticker  TEXT NOT NULL,
            close   REAL NOT NULL,
            PRIMARY KEY (date, ticker)
        )
    ''')

    # Sector History
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sector_history (
            date    TEXT NOT NULL,
            ticker  TEXT NOT NULL,
            close   REAL NOT NULL,
            PRIMARY KEY (date, ticker)
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_price ON price_history(ticker, date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_company_active ON company_list(is_active)')

    conn.commit()
    conn.close()

    print(f"✅ Database initialized successfully → {DB_PATH}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    init_database()
