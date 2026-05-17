import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import sys
import warnings

warnings.filterwarnings('ignore', category=RuntimeWarning)

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    filename='calculate_oneil_rs.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'

def init_oneil_rs_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS oneil_rs (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            rs_value REAL,
            rs_score REAL,
            rs_rating INTEGER,
            rs_1m REAL, rs_3m REAL, rs_6m REAL, rs_12m REAL,
            rs_relative REAL,
            rs_chart REAL,
            PRIMARY KEY (date, ticker)
        )
    ''')
    conn.commit()
    conn.close()
    print('✅ oneil_rs table ready (append-only)')

def calculate_oneil_rs(target_date=None):
    if target_date is None:
        conn = sqlite3.connect(DB_PATH)
        target_date = conn.execute('SELECT MAX(date) FROM price_history').fetchone()[0]
        conn.close()

    print(f'Calculating O\'Neil RS as of {target_date}...')

    conn = sqlite3.connect(DB_PATH)
    exists = conn.execute("SELECT 1 FROM oneil_rs WHERE date = ? LIMIT 1", (target_date,)).fetchone()
    if exists:
        print(f'✅ RS for {target_date} already exists. Skipping.')
        conn.close()
        return

    # Load price data
    price_dict = {}
    df = pd.read_sql("SELECT date, ticker, close FROM price_history WHERE date <= ? ORDER BY ticker, date", conn, params=(target_date,))
    df['date'] = pd.to_datetime(df['date'])
    for ticker, group in df.groupby('ticker'):
        price_dict[ticker] = group.set_index('date')['close']

    rs_df = calculate_rs_for_date(target_date, price_dict)  # reuse function from backfill if possible, simplified here
    if not rs_df.empty:
        rs_df.to_sql('oneil_rs', conn, if_exists='append', index=False)
        print(f'✅ Saved RS for {len(rs_df):,} tickers on {target_date}')
    conn.close()

def calculate_rs_for_date(...):  # placeholder - use same logic as backfill
    pass  # full code in backfill for now

if __name__ == "__main__":
    init_oneil_rs_table()
    calculate_oneil_rs()