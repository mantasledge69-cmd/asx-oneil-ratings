import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import sys
import yfinance as yf

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    filename='calculate_oneil_rs_backfill.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'

def init_oneil_rs_table(drop_existing=False):
    conn = sqlite3.connect(DB_PATH)
    if drop_existing:
        conn.execute('DROP TABLE IF EXISTS oneil_rs')
        print('🗑️ Dropped existing oneil_rs table for fresh schema')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS oneil_rs (
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
        )
    ''')
    conn.commit()
    conn.close()
    print('✅ oneil_rs table ready (append-only)')

def get_existing_dates():
    conn = sqlite3.connect(DB_PATH)
    dates = pd.read_sql("SELECT DISTINCT date FROM oneil_rs", conn)['date'].tolist()
    conn.close()
    return set(dates)

def calculate_rs_for_date(target_date, price_dict, axjo_series):
    results = []
    for ticker, series in price_dict.items():
        try:
            if len(series) < 60:
                continue
            current = series.iloc[-1] if len(series) > 0 else None
            if current is None or current <= 0:
                continue

            idx = series.index.get_loc(target_date) if target_date in series.index else len(series) - 1
            if idx < 30:
                continue

            p1m = series.iloc[max(0, idx - 21)]
            p3m = series.iloc[max(0, idx - 63)]
            p6m = series.iloc[max(0, idx - 126)]
            p12m = series.iloc[max(0, idx - 252)]

            r1m = (current / p1m - 1) * 100 if p1m > 0 else np.nan
            r3m = (current / p3m - 1) * 100 if p3m > 0 else np.nan
            r6m = (current / p6m - 1) * 100 if p6m > 0 else np.nan
            r12m = (current / p12m - 1) * 100 if p12m > 0 else np.nan

            rs_score = np.nanmean([r1m, r3m, r6m, r12m])

            rs_relative = rs_score  # simplified for now
            rs_chart = np.clip(rs_relative * 1.5, -350, 350)  # tuned scaling

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
                'rs_relative': round(rs_relative, 4),
                'rs_chart': round(rs_chart, 2)
            })
        except Exception as e:
            logging.warning(f"RS calc error {ticker} on {target_date}: {e}")

    if results:
        rs_df = pd.DataFrame(results)
        rs_df['rs_rating'] = pd.qcut(rs_df['rs_score'], q=99, labels=False, duplicates='drop') + 1
        return rs_df
    return pd.DataFrame()

def backfill_oneil_rs(months=13):
    print(f'🚀 Starting {months}-month RS backfill...')
    conn = sqlite3.connect(DB_PATH)
    df_prices = pd.read_sql("SELECT date, ticker, close FROM price_history ORDER BY ticker, date", conn)
    conn.close()

    if df_prices.empty:
        print("No price data")
        return

    df_prices['date'] = pd.to_datetime(df_prices['date'])
    price_dict = {ticker: group.set_index('date')['close'].sort_index() for ticker, group in df_prices.groupby('ticker')}

    print(f"Loaded {len(df_prices):,} price rows | {len(price_dict)} tickers")

    existing_dates = get_existing_dates()
    end_date = df_prices['date'].max()
    start_date = end_date - timedelta(days=months*31)

    trading_dates = sorted([d.strftime('%Y-%m-%d') for d in df_prices['date'].unique() if d >= start_date])

    print(f"Backfilling {len(trading_dates)} dates...")

    total_inserted = 0
    for i, d_str in enumerate(trading_dates):
        if d_str in existing_dates:
            continue

        try:
            rs_df = calculate_rs_for_date(d_str, price_dict, None)
            if not rs_df.empty:
                conn = sqlite3.connect(DB_PATH)
                rs_df.to_sql('oneil_rs', conn, if_exists='append', index=False)
                conn.close()
                total_inserted += len(rs_df)
                print(f"[ {d_str} ] ✅ Inserted {len(rs_df):,} records")

            if (i + 1) % 10 == 0 or i == len(trading_dates)-1:
                progress = (i+1) / len(trading_dates) * 100
                print(f"Progress: {i+1}/{len(trading_dates)} ({progress:.1f}%) | Total inserted: {total_inserted:,}")
        except Exception as e:
            logging.error(f"Backfill failed for {d_str}: {e}")
            print(f"❌ Error on {d_str}: {e}")

    print(f"🎉 Backfill complete! Inserted {total_inserted:,} rows")

if __name__ == "__main__":
    init_oneil_rs_table(drop_existing=True)  # Force fresh schema
    backfill_oneil_rs(months=13)
