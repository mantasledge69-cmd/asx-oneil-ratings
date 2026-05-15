# price_history_backfill.py
import sqlite3
import yfinance as yf
from datetime import datetime, timedelta
import time
import logging
from utils.ticker_utils import clean_ticker

logging.basicConfig(filename='price_history_backfill.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

print("🚀 Starting 2-Year STRICT Price History Backfill...")

conn = sqlite3.connect('ASX_history.db')
cur = conn.cursor()

# Active tickers
cur.execute("SELECT ticker FROM companies WHERE status = 'Active'")
tickers = [row[0] for row in cur.fetchall()]
print(f"Found {len(tickers)} active tickers")

backfill_start = (datetime.now() - timedelta(days=800)).strftime('%Y-%m-%d')
print(f"Backfilling from {backfill_start}...")

batch_size = 100
for i in range(0, len(tickers), batch_size):
    batch = tickers[i:i+batch_size]
    print(f"\n📦 Batch {i//batch_size + 1} | {len(batch)} tickers")
    
    for ticker in batch:
        try:
            clean = clean_ticker(ticker)
            df = yf.download(clean + ".AX", start=backfill_start, progress=False, auto_adjust=True)
            
            if df.empty:
                continue
                
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].reset_index()
            df['ticker'] = clean
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT OR REPLACE INTO price_history (date, ticker, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (row['Date'].strftime('%Y-%m-%d'), clean,
                      float(row['Open']), float(row['High']), float(row['Low']),
                      float(row['Close']), int(row['Volume'])))
            
            conn.commit()
            time.sleep(1.5)
            
        except Exception as e:
            logging.error(f"Error on {ticker}: {e}")
            continue
    
    print(f"   ✅ Batch completed")

print("🎉 2-Year backfill finished!")
conn.close()