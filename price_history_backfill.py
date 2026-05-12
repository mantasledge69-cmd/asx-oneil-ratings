import pandas as pd
import sqlite3
import yfinance as yf
import logging
from datetime import datetime, timedelta
import time

logging.basicConfig(
    filename='price_history_backfill.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'
BATCH_SIZE = 120
MAX_RETRIES = 3
SLEEP_BETWEEN_BATCHES = 4


def get_backfill_start(ticker, conn):
    """STRICT: Use updated_date from company_list as hard floor"""
    cursor = conn.cursor()
    
    # Get last price date
    cursor.execute("SELECT MAX(date) FROM price_history WHERE ticker = ?", (ticker,))
    result = cursor.fetchone()[0]
    
    if result:
        last_date = datetime.strptime(result, '%Y-%m-%d')
        resume_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        resume_date = None
    
    # Get updated_date from company_list (hard floor)
    cursor.execute("SELECT updated_date FROM company_list WHERE Ticker = ?", (ticker,))
    row = cursor.fetchone()
    updated_date = row[0] if row and row[0] else (datetime.now() - timedelta(days=395)).strftime('%Y-%m-%d')  # ~13 months fallback
    
    if resume_date:
        start_date = max(resume_date, updated_date)
    else:
        start_date = updated_date
    
    return start_date


def backfill_price_history():
    print("🚀 Starting STRICT updated_date ASX Price History Backfill...")
    logging.info("=== STRICT Price History Backfill Started ===")
    start_time = datetime.now()

    conn = sqlite3.connect(DB_PATH)
    
    df = pd.read_sql("SELECT Ticker FROM company_list WHERE is_active = 1 ORDER BY \"Market Cap Num\" DESC", conn)
    tickers = df['Ticker'].tolist()
    
    print(f"Found {len(tickers):,} active tickers")
    logging.info(f"Backfilling {len(tickers)} tickers using strict updated_date")

    success = 0
    failed = []

    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        batch_str = " ".join([t + ".AX" if not t.endswith('.AX') else t for t in batch])
        
        print(f"\n📦 Batch {i//BATCH_SIZE + 1} | {len(batch)} tickers")
        
        for attempt in range(MAX_RETRIES):
            try:
                data = yf.download(
                    batch_str,
                    period="max",
                    group_by='ticker',
                    auto_adjust=True,
                    threads=8,
                    progress=False
                )
                
                inserted = 0
                batch_tickers = []
                
                for ticker in batch:
                    try:
                        if len(batch) > 1 and ticker in data.columns.get_level_values(0):
                            ticker_data = data[ticker]['Close'].dropna()
                        elif len(batch) == 1:
                            ticker_data = data['Close'].dropna()
                        else:
                            continue
                            
                        if ticker_data.empty:
                            continue
                            
                        df_ticker = pd.DataFrame({
                            'date': ticker_data.index.strftime('%Y-%m-%d'),
                            'ticker': ticker,
                            'close': ticker_data.values
                        })
                        
                        start_date = get_backfill_start(ticker, conn)
                        df_ticker = df_ticker[df_ticker['date'] >= start_date]
                        
                        if not df_ticker.empty:
                            df_ticker.to_sql('price_history', conn, if_exists='append', index=False, method='multi')
                            inserted += len(df_ticker)
                            batch_tickers.append(ticker)
                            
                    except Exception as e_t:
                        logging.warning(f"Error processing {ticker}: {e_t}")
                        continue
                
                # Auto stamp updated_date for this batch
                if batch_tickers:
                    today = datetime.now().strftime('%Y-%m-%d')
                    placeholders = ','.join('?' * len(batch_tickers))
                    conn.execute(f"UPDATE company_list SET updated_date = ? WHERE Ticker IN ({placeholders})", [today] + batch_tickers)
                    conn.commit()
                
                print(f"   ✅ Inserted/Updated {inserted:,} records")
                logging.info(f"Batch complete - {inserted} new records")
                success += 1
                break
                
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = SLEEP_BETWEEN_BATCHES * (attempt + 2)
                    print(f"   ⚠️ Attempt {attempt+1} failed, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"   ❌ Batch failed")
                    failed.extend(batch)
                    logging.error(f"Batch failed: {e}")

        time.sleep(SLEEP_BETWEEN_BATCHES)

    # Final full stamp
    today = datetime.now().strftime('%Y-%m-%d')
    conn.execute("UPDATE company_list SET updated_date = ? WHERE is_active = 1", (today,))
    conn.commit()
    
    # Safe final summary BEFORE closing
    total_rows = conn.execute('SELECT COUNT(*) FROM price_history').fetchone()[0]
    today_inserted = inserted if 'inserted' in locals() else 0
    conn.close()
    
    duration = datetime.now() - start_time
    print(f"\n🎉 Backfill completed in {duration}")
    print(f"   Records inserted/updated today: {today_inserted}")
    print(f"   Total rows in price_history: {total_rows}")
    if failed:
        print(f"   Failed: {len(failed)}")
    logging.info(f"Backfill completed | Duration: {duration} | Total rows: {total_rows}")

if __name__ == "__main__":
    backfill_price_history()