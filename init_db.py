import sqlite3
import pandas as pd

def init_db():
    conn = sqlite3.connect('ASX_history.db')
    # Existing tables...
    conn.execute('''CREATE TABLE IF NOT EXISTS price_history (
        date TEXT,
        ticker TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY (date, ticker)
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS oneil_rs (
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        rs_value REAL,
        rs_score REAL,
        rs_rating INTEGER,
        rs_1m REAL,
        rs_3m REAL,
        rs_6m REAL,
        rs_12m REAL,
        rs_relative REAL,
        rs_chart REAL,
        PRIMARY KEY (date, ticker)
    )''')
    conn.commit()
    conn.close()
    print("✅ Database initialized with full oneil_rs schema")

if __name__ == "__main__":
    init_db()
