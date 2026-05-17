import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    filename='calculate_oneil_rs_backfill.log',
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
    print("✅ oneil_rs table ready (append-only)")

def get_existing_dates():
    conn = sqlite3.connect(DB_PATH)
    dates = pd.read_sql("SELECT DISTINCT date FROM oneil_rs", conn)['date'].tolist()
    conn.close()
    return set(dates)

def calculate_rs_for_date(target_date, df_prices):
    print(f"Calculating for {target_date}...")
    conn = sqlite3.connect(DB_PATH)
    exists = conn.execute("SELECT 1 FROM oneil_rs WHERE date = ? LIMIT 1", (target_date,)).fetchone()
    conn.close()
    if exists:
        print(f"✅ Skipping {target_date} (already exists)")
        return pd.DataFrame()

    df_day = df_prices[df_prices['date'] == target_date]
    if df_day.empty:
        return pd.DataFrame()

    results = []
    tickers = df_prices['ticker'].unique()
    for ticker in tickers:
        try:
            series = df_prices[df_prices['ticker'] == ticker].set_index('date')['close'].sort_index()
            if len(series) < 60:
                continue
            current = series.asof(target_date)
            if pd.isna(current):
                continue

            p1m = series.asof(pd.to_datetime(target_date) - timedelta(days=30))
            p3m = series.asof(pd.to_datetime(target_date) - timedelta(days=90))
            p6m = series.asof(pd.to_datetime(target_date) - timedelta(days=180))
            p12m = series.asof(pd.to_datetime(target_date) - timedelta(days=365))

            r1m = (current / p1m - 1) * 100 if pd.notna(p1m) and p1m > 0 else np.nan
            r3m = (current / p3m - 1) * 100 if pd.notna(p3m) and p3m > 0 else np.nan
            r6m = (current / p6m - 1) * 100 if pd.notna(p6m) and p6m > 0 else np.nan
            r12m = (current / p12m - 1) * 100 if pd.notna(p12m) and p12m > 0 else np.nan

            rs_score = np.nanmean([r1m, r3m, r6m, r12m])

            results.append({
                'date': target_date,
                'ticker': ticker,
                'rs_value': round(rs_score, 4),
                'rs_score': round(rs_score, 4),
                'rs_rating': None,
                'rs_1m': round(r1m, 2) if not np.isnan(r1m) else None,
                'rs_3m': round(r3m, 2) if not np.isnan(r3m) else None,
                'rs_6m': round(r6m, 2) if not np.isnan(r6m) else None,
                'rs_12m': round(r12m, 2) if not np.isnan(r12m) else None,
                'rs_relative': round(rs_score, 4),  # simplified
                'rs_chart': round(rs_score * 2, 2)  # temporary scaling
            })
        except:
            continue

    if results:
        rs_df = pd.DataFrame(results)
        valid_scores = rs_df['rs_score'].dropna()
        if not valid_scores.empty:
            rs_df['rs_rating'] = pd.qcut(valid_scores, q=99, labels=False, duplicates='drop') + 1
            rs_df['rs_rating'] = rs_df['rs_rating'].reindex(rs_df.index, fill_value=50)
        else:
            rs_df['rs_rating'] = 50
        return rs_df
    return pd.DataFrame()

def backfill_oneil_rs(months=12):
    print(f"🚀 Starting {months}-month RS backfill...")
    conn = sqlite3.connect(DB_PATH)
    df_prices = pd.read_sql("""
        SELECT date, ticker, close 
        FROM price_history 
        WHERE date >= DATE('now', '-500 days')
        ORDER BY ticker, date
    """, conn)
    conn.close()

    if df_prices.empty:
        print("No price data")
        return

    df_prices['date'] = pd.to_datetime(df_prices['date']).dt.strftime('%Y-%m-%d')
    existing_dates = get_existing_dates()

    unique_dates = sorted([d for d in df_prices['date'].unique() if d])
    start_idx = max(0, len(unique_dates) - 280)  # ~12 months
    target_dates = unique_dates[start_idx:]

    print(f"Backfilling {len(target_dates)} dates...")

    for d in target_dates:
        if d in existing_dates:
            continue
        rs_df = calculate_rs_for_date(d, df_prices)
        if not rs_df.empty:
            conn = sqlite3.connect(DB_PATH)
            rs_df.to_sql('oneil_rs', conn, if_exists='append', index=False)
            conn.close()
            print(f"✅ Inserted {len(rs_df)} records for {d}")

    print("🎉 Backfill complete!")

if __name__ == "__main__":
    init_oneil_rs_table()
    backfill_oneil_rs(months=12)