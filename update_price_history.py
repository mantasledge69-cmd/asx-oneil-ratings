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
    print("🚀 Starting Price History Update (v5 - Defensive Column Fix)...")
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
            ticker = row['ASX code'] + '.AX'
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
                    # Force clean DataFrame
                    data = data.reset_index()
                    data = data[['Date', 'Close']].copy()
                    data.columns = ['date', 'close']
                    data['ticker'] = ticker
                    
                    # Insert only the exact columns that exist
                    insert_data = data[['date', 'ticker', 'close']]
                    
                    insert_data.to_sql('price_history', conn, if_exists='append', index=False)
                    
                    # Update last successful date
                    conn.execute('''
                        UPDATE company_list 
                        SET updated_price_date = ? 
                        WHERE "ASX code" = ?
                    ''', (today, row['ASX code']))
                    
                    success_count += 1
                    print(f"✅ {len(data)} rows")
                else:
                    print("⚠️ No data")
                    failed.append((ticker, "No data"))

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Failed - {error_msg[:80]}")
                logging.error(f"Failed {ticker}: {error_msg}")
                failed.append((ticker, error_msg[:80]))

            time.sleep(0.7)

        conn.commit()
        conn.close()

        print(f"\n✅ Price Update Complete!")
        print(f"   Successfully updated : {success_count} companies")
        print(f"   Failed               : {len(failed)}")

        if failed:
            print("\nFirst 10 failed:")
            for t, reason in failed[:10]:
                print(f"   {t} → {reason}")

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        logging.error(f"Critical failure: {e}", exc_info=True)

if __name__ == "__main__":
    update_price_history()