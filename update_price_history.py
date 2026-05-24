import pandas as pd
import yfinance as yf
import sqlite3
import logging
from datetime import datetime, timedelta
import time

logging.basicConfig(
    filename='update_price_history.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'

def update_price_history():
    print("🚀 Starting Price History Update (v12 - Robust Column Handling)...")
    logging.info("=== Price History Update Started ===")

    try:
        conn = sqlite3.connect(DB_PATH)
        
        df = pd.read_sql("""
            SELECT "ASX code", updated_price_date 
            FROM company_list 
            WHERE is_active = 1
            ORDER BY "ASX code"
        """, conn)
        
        print(f"Found {len(df)} active companies to update\n")

        today = datetime.now().strftime('%Y-%m-%d')
        success_count = 0
        failed = []

        for idx, row in enumerate(df.iterrows(), 1):
            _, row = row
            asx_code = row['ASX code']
            ticker = asx_code + '.AX'
            start_date = row['updated_price_date']
            
            print(f"[{idx:4d}/{len(df)}] {ticker} from {start_date}...", end=' ')
            
            try:
                data = yf.download(
                    ticker, 
                    start=start_date, 
                    end=today, 
                    progress=False, 
                    auto_adjust=True,
                    timeout=10
                )
                
                if not data.empty:
                    # Robust close price extraction
                    if 'Close' in data.columns:
                        close_series = data['Close']
                    elif 'Adj Close' in data.columns:
                        close_series = data['Adj Close']
                    else:
                        close_series = data.iloc[:, 3]  # fallback to 4th column
                    
                    closes = close_series.reset_index()
                    closes.columns = ['date', 'close']
                    closes['ASX code'] = asx_code
                    closes['date'] = closes['date'].dt.strftime('%Y-%m-%d')
                    
                    closes[['date', 'ASX code', 'close']].to_sql('price_history', conn, if_exists='append', index=False)
                    
                    # Update last successful date
                    last_date = closes['date'].max()
                    conn.execute('''
                        UPDATE company_list 
                        SET updated_price_date = ? 
                        WHERE "ASX code" = ?
                    ''', (last_date, asx_code))
                    
                    success_count += 1
                    print(f"✅ {len(closes)} rows")
                else:
                    print("⚠️ No data")
                    failed.append((ticker, "No data"))

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Failed - {error_msg[:100]}")
                logging.error(f"Failed {ticker}: {error_msg}")
                failed.append((ticker, error_msg[:100]))

            time.sleep(0.7)

        conn.commit()
        conn.close()

        print(f"\n✅ Price History Update Complete!")
        print(f"   Successfully updated : {success_count} companies")
        print(f"   Failed               : {len(failed)} companies")

        if failed:
            print("\nFirst 10 failed:")
            for t, reason in failed[:10]:
                print(f"   {t} → {reason}")

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        logging.error(f"Critical failure: {e}", exc_info=True)

if __name__ == "__main__":
    update_price_history()