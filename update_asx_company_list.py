import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    filename='update_asx_company_list.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'
DIRECTORY_URL = "https://asx.api.markitdigital.com/asx-research/1.0/companies/directory/file?"

def init_company_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS company_list (
            Ticker TEXT PRIMARY KEY,
            "ASX code" TEXT,
            Company TEXT,
            Industry_Group TEXT,
            "Market Cap" TEXT,
            "Market Cap Num" REAL,
            listing_date TEXT,
            updated_date TEXT,
            is_active INTEGER DEFAULT 1,
            last_updated TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Company list table structure verified")

def update_company_list():
    print("🚀 Updating ASX Company Master List (Robust v17 - Enhanced Recovery)...")
    logging.info("=== Company List Update Started ===")

    try:
        df = pd.read_csv(DIRECTORY_URL, dtype=str, quotechar='"', on_bad_lines='skip')
        df.columns = [col.strip().replace('"', '').strip() for col in df.columns]
        print(f"Downloaded {len(df):,} records | Columns: {list(df.columns)}")

        df = df.rename(columns={
            'Company name': 'Company',
            'GICs industry group': 'Industry_Group',
            'Listing date': 'listing_date'
        })

        df['Market Cap'] = df['Market Cap'].astype(str).str.strip()

        active_mask = (
            df['Market Cap'].notna() &
            ~df['Market Cap'].isin(['SUSPENDED', '--', '', '0', 'nan']) &
            df['Market Cap'].str.replace(r'[^0-9]', '', regex=True).str.len() > 0
        )

        active_df = df[active_mask].copy()
        suspended_df = df[~active_mask].copy()

        print(f"Detected Active: {len(active_df)} | Suspended: {len(suspended_df)}")

        # Process
        active_df['Market Cap Num'] = pd.to_numeric(active_df['Market Cap'].str.replace(',', '', regex=False), errors='coerce')
        active_df = active_df.dropna(subset=['ASX code']).copy()
        active_df['Ticker'] = active_df['ASX code'].str.strip() + '.AX'
        active_df['is_active'] = 1

        suspended_df['Ticker'] = suspended_df['ASX code'].str.strip() + '.AX'
        suspended_df['is_active'] = 0
        suspended_df['Market Cap Num'] = 0.0

        all_df = pd.concat([active_df, suspended_df], ignore_index=True).drop_duplicates(subset=['Ticker'])

        # === Robustness: Load old data and recover missing ===
        conn = sqlite3.connect(DB_PATH)
        old_df = pd.read_sql("SELECT * FROM company_list", conn)
        old_set = set(old_df['Ticker'])

        current_tickers = set(all_df['Ticker'])
        missing_tickers = old_set - current_tickers
        new_tickers = current_tickers - old_set

        print(f"Missing from previous DB (will be recovered): {len(missing_tickers)}")

        # Smart updated_date preservation
        old_date_dict = dict(zip(old_df['Ticker'], old_df['updated_date']))

        def get_updated_date(ticker):
            return old_date_dict.get(ticker) or (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

        all_df['updated_date'] = all_df['Ticker'].apply(get_updated_date)
        all_df['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        final_cols = ['Ticker', 'ASX code', 'Company', 'Industry_Group',
                     'Market Cap', 'Market Cap Num', 'listing_date', 
                     'updated_date', 'is_active', 'last_updated']

        master_df = all_df[final_cols].copy()

        # Save
        master_df.to_sql('company_list', conn, if_exists='replace', index=False)
        conn.close()

        print(f"✅ TOTAL: {len(master_df):,} companies")
        print(f"   Active: {len(active_df):,} | Suspended: {len(suspended_df):,}")
        print(f"   New: {len(new_tickers)} | Recovered missing: {len(missing_tickers)}")

        if missing_tickers:
            print(f"   Recovered examples: {sorted(list(missing_tickers))[:6]}...")
        if new_tickers:
            print(f"   New examples: {sorted(list(new_tickers))[:6]}...")

        logging.info(f"Updated | Total: {len(master_df)} | Active: {len(active_df)} | Recovered: {len(missing_tickers)}")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Update failed: {e}", exc_info=True)

if __name__ == "__main__":
    init_company_table()
    update_company_list()