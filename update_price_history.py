import pandas as pd
import yfinance as yf
import sqlite3
import logging
from datetime import datetime, timedelta
import time
import os
import pickle

# === PROJECT LOGGING (per-file .log as required) ===
logging.basicConfig(
    filename='update_price_history.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'
PKL_DIR = 'data/pkl'

os.makedirs(PKL_DIR, exist_ok=True)


def get_fresh_pkl(asx_code: str, max_age_hours: int = 24):
    """Load cached yfinance data from pkl if it exists and is fresh (today or within max_age_hours)."""
    pkl_path = os.path.join(PKL_DIR, f"{asx_code}.pkl")
    if os.path.exists(pkl_path):
        try:
            file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(pkl_path))
            if file_age.total_seconds() < (max_age_hours * 3600):
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
                return data, True  # fresh pkl loaded
        except Exception as e:
            logging.warning(f"Failed to load pkl for {asx_code}: {e}")
    return None, False


def save_to_pkl(asx_code: str, data):
    """Save full yfinance DataFrame to pkl for future speed."""
    pkl_path = os.path.join(PKL_DIR, f"{asx_code}.pkl")
    try:
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        logging.info(f"Saved fresh pkl cache for {asx_code}")
    except Exception as e:
        logging.error(f"Failed to save pkl for {asx_code}: {e}")


def update_price_history():
    print("Starting Price History Update (v13 - PKL Caching Enabled)...")
    logging.info("=== Price History Update Started (with daily pkl caching) ===")

    try:
        conn = sqlite3.connect(DB_PATH)
        
        df = pd.read_sql("""
            SELECT "ASX code", updated_price_date 
            FROM company_list 
            WHERE is_active = 1
            ORDER BY "ASX code"
        """, conn)
        
        print(f"Found {len(df)} active companies to update (pkl cache will be used when fresh)\n")

        today = datetime.now().strftime('%Y-%m-%d')
        success_count = 0
        failed = []
        pkl_hits = 0

        for idx, row in enumerate(df.iterrows(), 1):
            _, row = row
            asx_code = row['ASX code']
            ticker = asx_code + '.AX'
            start_date = row['updated_price_date']
            
            print(f"[{idx:4d}/{len(df)}] {ticker} from {start_date}...", end=' ')
            
            # === PKL CACHING LOGIC (core requirement) ===
            data, used_pkl = get_fresh_pkl(asx_code)
            
            if used_pkl and not data.empty:
                pkl_hits += 1
                print(" [PKL HIT - instant]", end=' ')
            else:
                # Only call Yahoo Finance if no fresh pkl
                try:
                    data = yf.download(
                        ticker, 
                        start=start_date, 
                        end=today, 
                        progress=False, 
                        auto_adjust=True,
                        timeout=15
                    )
                    if not data.empty:
                        save_to_pkl(asx_code, data)  # cache for next run
                    
                except Exception as e:
                    error_msg = str(e)
                    print(f" Failed YF - {error_msg[:80]}")
                    logging.error(f"YF download failed {ticker}: {error_msg}")
                    failed.append((ticker, error_msg[:100]))
                    time.sleep(0.7)
                    continue
            
            if not data.empty:
                try:
                    # Robust close price extraction (same as before)
                    if 'Close' in data.columns:
                        close_series = data['Close']
                    elif 'Adj Close' in data.columns:
                        close_series = data['Adj Close']
                    else:
                        close_series = data.iloc[:, 3]
                    
                    closes = close_series.reset_index()
                    closes.columns = ['date', 'close']
                    closes['ASX code'] = asx_code
                    closes['date'] = closes['date'].dt.strftime('%Y-%m-%d')
                    
                    # Drop rows with missing/invalid close prices.
                    # yfinance often returns NaN closes for illiquid or suspended stocks.
                    closes['close'] = pd.to_numeric(closes['close'], errors='coerce')
                    closes = closes.dropna(subset=['close'])
                    
                    if closes.empty:
                        print(" no valid close prices (all NaN)")
                        failed.append((ticker, "No valid close prices"))
                        time.sleep(0.5)
                        continue
                    
                    # Filter to only dates newer than what we already have in DB.
                    # This is critical for safety with PKL caching + when re-running yf.download
                    # with a start_date that overlaps previously inserted data.
                    cur = conn.cursor()
                    cur.execute('SELECT MAX(date) FROM price_history WHERE "ASX code" = ?', (asx_code,))
                    max_existing = cur.fetchone()[0]
                    if max_existing:
                        closes = closes[closes['date'] > max_existing]
                    
                    if closes.empty:
                        print(" up to date (no new rows)")
                    else:
                        # Append only truly new rows (prevents UNIQUE constraint violation)
                        closes[['date', 'ASX code', 'close']].to_sql('price_history', conn, if_exists='append', index=False)
                        
                        # Update last successful date in company_list
                        last_date = closes['date'].max()
                        conn.execute('''
                            UPDATE company_list 
                            SET updated_price_date = ? 
                            WHERE "ASX code" = ?
                        ''', (last_date, asx_code))
                        
                        success_count += 1
                        print(f" {len(closes)} new rows {'(from pkl)' if used_pkl else '(from YF + cached)'}")
                except Exception as e:
                    error_msg = str(e)
                    print(f" Failed processing - {error_msg[:80]}")
                    logging.error(f"Processing failed {ticker}: {error_msg}")
                    failed.append((ticker, error_msg[:100]))
                    time.sleep(0.5)
                    continue
            else:
                print(" No new data")
                failed.append((ticker, "No data"))

            time.sleep(0.5)  # polite delay

        conn.commit()
        conn.close()

        print(f"\n Price History Update Complete!")
        print(f"   Successfully updated : {success_count} companies")
        print(f"   PKL cache hits       : {pkl_hits} (instant, no YF call)")
        print(f"   Failed               : {len(failed)} companies")

        if failed:
            print("\nFirst 10 failed:")
            for t, reason in failed[:10]:
                print(f"   {t} → {reason}")

        logging.info(f"Update finished. Success={success_count}, PKL hits={pkl_hits}, Failed={len(failed)}")

    except Exception as e:
        print(f" Critical Error: {e}")
        logging.error(f"Critical failure: {e}", exc_info=True)


if __name__ == "__main__":
    update_price_history()