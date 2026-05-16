# price_history_backfill.py
import sqlite3
import yfinance as yf
import time
import logging
import pandas as pd
from datetime import datetime, timedelta
from utils.ticker_utils import clean_ticker

logging.basicConfig(filename='price_history_backfill.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

print("🚀 Starting Robust Adaptive Batched Backfill...")

conn = sqlite3.connect('ASX_history.db')
cur = conn.cursor()

cur.execute("""
    SELECT "Ticker", updated_date 
    FROM company_list 
    WHERE is_active = 1
    ORDER BY updated_date ASC NULLS FIRST
""")
rows = cur.fetchall()

print(f"Found {len(rows)} active tickers")

today_str = datetime.now().strftime('%Y-%m-%d')
i = 0

while i < len(rows):
    # Determine batch size based on how old the data is
    raw_ticker, last_updated = rows[i]
    if last_updated and last_updated != 'None':
        gap_days = (datetime.now().date() - datetime.strptime(last_updated, '%Y-%m-%d').date()).days
    else:
        gap_days = 999

    batch_size = 2 if gap_days > 60 else 3 if gap_days > 14 else 4
    batch = rows[i : i + batch_size]
    clean_tickers = [clean_ticker(r[0]) for r in batch]
    raw_map = {clean_ticker(r[0]): r[0] for r in batch}

    print(f"\n📦 Batch {i//batch_size + 1} | Size {len(batch)} | Gap ~{gap_days}d | First: {clean_ticker(raw_ticker)}")

    try:
        # Find oldest date in this batch for start
        valid_dates = [r[1] for r in batch if r[1] and r[1] != 'None']
        start_str = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
        if valid_dates:
            oldest = min(valid_dates)
            start_str = datetime.strptime(oldest, '%Y-%m-%d') 

        print(f"   Pulling from {start_str}...")

        df_multi = yf.download(clean_tickers, start=start_str, progress=False, auto_adjust=True, group_by='ticker')

        for clean in clean_tickers:
            raw = raw_map[clean]
            try:
                # Safe extraction
                if len(clean_tickers) > 1 and clean in df_multi.columns:
                    ticker_df = df_multi[clean][['Close']].dropna()
                else:
                    ticker_df = df_multi[['Close']].dropna() if not df_multi.empty else pd.DataFrame()

                if ticker_df.empty:
                    print(f"   ⚠️  {clean} skipped (no data)")
                    continue

                ticker_df = ticker_df.reset_index()
                ticker_df['Date'] = pd.to_datetime(ticker_df['Date']).dt.strftime('%Y-%m-%d')

                inserted = 0
                for _, row in ticker_df.iterrows():
                    close_val = float(row['Close'].iloc[0] if hasattr(row['Close'], 'iloc') else row['Close'])
                    cur.execute("""
                        INSERT OR REPLACE INTO price_history (date, ticker, close)
                        VALUES (?, ?, ?)
                    """, (row['Date'], clean, close_val))
                    inserted += 1

                cur.execute("""
                    UPDATE company_list 
                    SET updated_date = ? 
                    WHERE "Ticker" = ?
                """, (today_str, raw))
                conn.commit()

                print(f"   ✅ {clean} | +{inserted} prices | stamped")

            except Exception as e:
                print(f"   ❌ {clean} error: {e}")
                continue

    except Exception as e:
        print(f"   ❌ Batch failed: {e}")

    i += len(batch)          # Move to next unprocessed batch
    time.sleep(1.0 if gap_days > 30 else 0.2)

print("🎉 Robust adaptive batched backfill completed!")
conn.close()