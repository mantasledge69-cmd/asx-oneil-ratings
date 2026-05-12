import pandas as pd
import sqlite3
import yfinance as yf
import logging
from datetime import datetime, timedelta
import time
from tqdm import tqdm
import os

logging.basicConfig(
    filename='price_history_backfill.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'
BATCH_SIZE = 120          # Increased for speed
MAX_RETRIES = 3
SLEEP_BETWEEN_BATCHES = 4 # Reduced
THREADS = 8

def init_db_if_needed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            date TEXT,
            ticker TEXT,
            close REAL,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.commit()
    conn.close()

def get_backfill_start(ticker, conn):
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) FROM price_history WHERE ticker = ?", (ticker,))
    result = cursor.fetchone()[0]
    
    if result:
        return (datetime.strptime(result, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    cursor.execute("SELECT listing_date, updated_date FROM company_list WHERE Ticker = ?", (ticker,))
    row = cursor.fetchone()
    if row and row[0]:
        return row[0]
    elif row and row[1]:
        return row[1]
    else:
        return (datetime.now() - timedelta(days=1095)).strftime('%Y-%m-%d')  # ~3 years fallback

def backfill_price_history():
    print("🚀 Starting FAST ASX Price History Backfill...")
    logging.info("=== FAST Price History Backfill Started ===")
    start_time = datetime.now()

    init_db_if_needed()
    conn = sqlite3.connect(DB_PATH)
    
    # Get active companies
    df = pd.read_sql("SELECT Ticker FROM company_list WHERE is_active = 1 ORDER BY \"Market Cap Num\" DESC", conn)
    tickers = [t + ".AX" if not t.endswith(".AX") else t for t in df['Ticker'].tolist()]
    
    print(f"Found {len(tickers):,} tickers")
    logging.info(f"Backfilling {len(tickers)} tickers")

    success_count = 0
    total_inserted = 0
    failed = []

    pbar = tqdm(total=len(tickers), desc="Overall Progress")

    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        batch_str = " ".join(batch)
        
        print(f"\n📦 Batch {i//BATCH_SIZE + 1} | {len(batch)} tickers")
        
        for attempt in range(MAX_RETRIES):
            try:
                data = yf.download(
                    batch_str,
                    period="max",
                    group_by='ticker',
                    auto_adjust=True,
                    threads=THREADS,
                    progress=False,
                    prepost=False
                )
                
                if data.empty:
                    raise ValueError("Empty data")
                
                inserted = 0
                conn_local = sqlite3.connect(DB_PATH)  # fresh connection
                
                for ticker_raw in batch:
                    ticker = ticker_raw.replace(".AX", "")
                    try:
                        if len(batch) > 1:
                            ticker_data = data[ticker_raw]['Close'].dropna()
                        else:
                            ticker_data = data['Close'].dropna()
                        
                        if ticker_data.empty:
                            continue
                        
                        df_ticker = pd.DataFrame({
                            'date': ticker_data.index.strftime('%Y-%m-%d'),
                            'ticker': ticker,
                            'close': ticker_data.values
                        })
                        
                        start_date = get_backfill_start(ticker, conn_local)
                        df_ticker = df_ticker[df_ticker['date'] >= start_date]
                        
                        if not df_ticker.empty:
                            df_ticker.to_sql('price_history', conn_local, if_exists='append', index=False, method='multi')
                            inserted += len(df_ticker)
                    except Exception as e_t:
                        logging.warning(f"Error processing {ticker}: {e_t}")
                        continue
                
                conn_local.close()
                print(f"   ✅ Inserted ~{inserted:,} records")
                logging.info(f"Batch done - {inserted} new records")
                success_count += 1
                total_inserted += inserted
                pbar.update(len(batch))
                break
                
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = SLEEP_BETWEEN_BATCHES * (2 ** attempt)
                    print(f"   ⚠️ Retry {attempt+1} in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"   ❌ Batch failed")
                    failed.extend(batch)
                    pbar.update(len(batch))
                    logging.error(f"Batch failed: {e}")
        
        time.sleep(SLEEP_BETWEEN_BATCHES)

    pbar.close()
    conn.close()
    
    duration = datetime.now() - start_time
    print(f"\n🎉 Backfill completed in {duration}")
    print(f"   Total records inserted: {total_inserted:,}")
    if failed:
        print(f"   Failed: {len(failed)} tickers")
    
    logging.info(f"Backfill finished | Duration: {duration} | Inserted: {total_inserted} | Failed: {len(failed)}")

if __name__ == "__main__":
    backfill_price_history()
