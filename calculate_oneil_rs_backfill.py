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
            rs_1m REAL, rs_3m REAL, rs_6m REAL, rs_12m REAL,
            rs_relative REAL,
            rs_chart REAL,
            PRIMARY KEY (date, ticker)
        )
    ''')
    conn.commit()
    conn.close()
    print('✅ oneil_rs table ready (append-only)')

def get_price_dict():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT date, ticker, close FROM price_history ORDER BY ticker, date", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    price_dict = {}
    for ticker, group in df.groupby('ticker'):
        price_dict[ticker] = group.set_index('date')['close'].sort_index()
    return price_dict

def calculate_rs_for_date(target_date, price_dict, axjo_series=None):
    results = []
    current_dt = pd.to_datetime(target_date)

    for ticker, series in price_dict.items():
        try:
            if len(series) < 60 or current_dt not in series.index:
                continue

            current = series[current_dt]
            idx = series.index.get_loc(current_dt)

            p1m = series.iloc[max(0, idx-21)]
            p3m = series.iloc[max(0, idx-63)]
            p6m = series.iloc[max(0, idx-126)]
            p12m = series.iloc[max(0, idx-252)]

            r1m  = (current / p1m - 1) * 100 if p1m > 0 else np.nan
            r3m  = (current / p3m - 1) * 100 if p3m > 0 else np.nan
            r6m  = (current / p6m - 1) * 100 if p6m > 0 else np.nan
            r12m = (current / p12m - 1) * 100 if p12m > 0 else np.nan

            returns = [r for r in [r1m, r3m, r6m, r12m] if not np.isnan(r)]
            rs_score = np.mean(returns) if returns else np.nan

            if np.isnan(rs_score):
                continue

            rs_rating = None  # will be filled later

            rs_chart = np.clip(rs_score * 2.5, -350, 350)  # tuned scaling

            results.append({
                'date': target_date,
                'ticker': ticker,
                'rs_value': round(rs_score, 4),
                'rs_score': round(rs_score, 4),
                'rs_rating': rs_rating,
                'rs_1m': round(r1m, 2) if not np.isnan(r1m) else None,
                'rs_3m': round(r3m, 2) if not np.isnan(r3m) else None,
                'rs_6m': round(r6m, 2) if not np.isnan(r6m) else None,
                'rs_12m': round(r12m, 2) if not np.isnan(r12m) else None,
                'rs_relative': round(rs_score, 4),
                'rs_chart': round(rs_chart, 2)
            })
        except Exception as e:
            logging.warning(f"Error {ticker} {target_date}: {e}")

    if results:
        rs_df = pd.DataFrame(results)
        # Fill ratings
        if len(rs_df) > 10:
            rs_df['rs_rating'] = pd.qcut(rs_df['rs_score'], q=99, labels=False, duplicates='drop') + 1
        return rs_df
    return pd.DataFrame()

def backfill_oneil_rs(months=13):
    print(f'🚀 Starting {months}-month RS backfill...')
    price_dict = get_price_dict()
    print(f'Loaded {sum(len(s) for s in price_dict.values()):,} price rows | {len(price_dict)} tickers')

    conn = sqlite3.connect(DB_PATH)
    existing = pd.read_sql("SELECT DISTINCT date FROM oneil_rs", conn)['date'].tolist()
    conn.close()
    existing = set(existing)

    dates = sorted([d.strftime('%Y-%m-%d') for d in price_dict[list(price_dict.keys())[0]].index if d.strftime('%Y-%m-%d') not in existing])
    dates = dates[-int(months*21):]  # approx trading days

    print(f'Backfilling {len(dates)} dates...')

    total_inserted = 0
    for i, d in enumerate(dates):
        try:
            rs_df = calculate_rs_for_date(d, price_dict)
            if not rs_df.empty:
                conn = sqlite3.connect(DB_PATH)
                rs_df.to_sql('oneil_rs', conn, if_exists='append', index=False)
                conn.close()
                print(f'[ {d} ] ✅ Inserted {len(rs_df)} records')
                total_inserted += len(rs_df)
                if (i+1) % 10 == 0:
                    print(f'Progress: {i+1}/{len(dates)} ({(i+1)/len(dates)*100:.1f}%) | Total inserted: {total_inserted:,}')
        except Exception as e:
            logging.error(f'Failed {d}: {e}')

    print(f'🎉 Backfill complete! Inserted {total_inserted:,} rows')

if __name__ == "__main__":
    init_oneil_rs_table(drop_existing=True)
    backfill_oneil_rs()