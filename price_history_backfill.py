import pandas as pd
import sqlite3
import yfinance as yf
import logging
from datetime import datetime, timedelta
import time
import os
from tqdm import tqdm

logging.basicConfig(
    filename='price_history_backfill.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'
BATCH_SIZE = 50
MAX_RETRIES = 3
SLEEP_BETWEEN_BATCHES = 8   # seconds - be kind to YF

def get_backfill_start(ticker, conn):
    """Get the earliest date we should backfill from"""
    cursor = conn.cursor()
    cursor.execute("SELECT MIN(date) FROM price_history WHERE ticker = ?", (ticker,))
    result = cursor.fetchone()[0]
    
    if result:
        # Already have some data → continue from last date
        return (datetime.strptime(result, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # New ticker → use listing_date or updated_date
    cursor.execute("SELECT listing_date, updated_date FROM company_list WHERE Ticker = ?", (ticker,))
    row = cursor.fetchone()
    if row and row[0]:
        return row[0]
    elif row and row[1]:
        return row[1]
    else:
        return (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')  # fallback 2 years

def backfill_price_history():
    print("🚀 Starting ASX Price History Backfill (Batch Mode)...")
    logging.info("=== Price History Backfill Started ===")
    start_time = datetime.now()

    conn = sqlite3.connect(DB_PATH)
    
    # Get active companies
    df = pd.read_sql("SELECT Ticker, Company FROM company_list WHERE is_active = 1 ORDER BY \"Market Cap Num\" DESC", conn)
    tickers = df['Ticker'].tolist()
    
    print(f"Found {len(tickers):,} active tickers to backfill")
    logging.info(f"Backfilling {len(tickers)} tickers")

    success = 0
    failed = []

    # Process in batches
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        batch_str = " ".join(batch)
        
        print(f"\n📦 Processing batch {i//BATCH_SIZE + 1}/{(len(tickers)+BATCH_SIZE-1)//BATCH_SIZE} → {len(batch)} tickers")
        
        for attempt in range(MAX_RETRIES):
            try:
                data = yf.download(
                    batch_str,
                    start=None,           # let yfinance handle start per ticker where possible
                    period="max",
                    group_by='ticker',
                    auto_adjust=True,
                    threads=True
                )
                
                if data.empty:
                    raise ValueError("Empty download")
                
                inserted = 0
                
                for ticker in batch:
                    try:
                        if len(batch) > 1:
                            ticker_data = data[ticker]['Close'].dropna()
                        else:
                            ticker_data = data['Close'].dropna()
                            
                        if ticker_data.empty:
                            continue
                            
                        df_ticker = pd.DataFrame({
                            'date': ticker_data.index.strftime('%Y-%m-%d'),
                            'ticker': ticker,
                            'close': ticker_data.values
                        })
                        
                        # Get start date for this ticker
                        start_date = get_backfill_start(ticker, conn)
                        df_ticker = df_ticker[df_ticker['date'] >= start_date]
                        
                        if not df_ticker.empty:
                            df_ticker.to_sql('price_history', conn, if_exists='append', index=False)
                            inserted += len(df_ticker)
                            
                    except Exception as e_t:
                        logging.warning(f"Error on {ticker}: {e_t}")
                        continue
                
                print(f"   ✅ Inserted/Updated {inserted:,} price records")
                logging.info(f"Batch complete - {inserted} new records")
                success += 1
                break
                
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = SLEEP_BETWEEN_BATCHES * (attempt + 2)
                    print(f"   ⚠️ Batch failed (attempt {attempt+1}), retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"   ❌ Batch failed after {MAX_RETRIES} attempts")
                    failed.extend(batch)
                    logging.error(f"Batch failed: {e}")

        time.sleep(SLEEP_BETWEEN_BATCHES)  # polite delay between batches

    conn.close()
    
    duration = datetime.now() - start_time
    print(f"\n🎉 Backfill finished in {duration}")
    print(f"   Successful batches: {success}/{len(tickers)//BATCH_SIZE + 1}")
    if failed:
        print(f"   Failed tickers: {len(failed)} → check log")
    
    logging.info(f"Backfill completed | Duration: {duration} | Failed: {len(failed)}")

if __name__ == "__main__":
    backfill_price_history()
