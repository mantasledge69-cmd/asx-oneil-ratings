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
    """Ensure company_list table has required structure"""
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
    print("🚀 Updating ASX Company Master List (Robust v2 with dropped ticker handling)...")
    logging.info("=== Company List Update Started ===")

    try:
        # Fetch latest from ASX
        df = pd.read_csv(DIRECTORY_URL, dtype=str)
        df.columns = [col.strip().replace('"', '').strip() for col in df.columns]

        print(f"Downloaded {len(df):,} total records from ASX")

        # Active vs Suspended detection
        active_mask = (
            ~df['Market Cap'].isin(['SUSPENDED', '--', '', '0', None]) &
            df['Market Cap'].str.replace(',', '', regex=False)
                           .str.replace('.', '', regex=False)
                           .str.isnumeric()
        )

        active_df = df[active_mask].copy()
        suspended_df = df[~active_mask].copy()

        # Process Active
        active_df['Market Cap Num'] = pd.to_numeric(
            active_df['Market Cap'].str.replace(',', '', regex=False), errors='coerce'
        )
        active_df = active_df.dropna(subset=['Market Cap Num', 'ASX code']).copy()
        active_df['Ticker'] = active_df['ASX code'] + '.AX'
        active_df['is_active'] = 1

        # Process Suspended/Delisted
        suspended_df['Ticker'] = suspended_df['ASX code'] + '.AX'
        suspended_df['is_active'] = 0
        suspended_df['Market Cap Num'] = 0

        all_df = pd.concat([active_df, suspended_df], ignore_index=True)

        # Load existing data for change detection
        conn = sqlite3.connect(DB_PATH)
        old_df = pd.read_sql("SELECT Ticker, is_active FROM company_list", conn)
        old_set = set(old_df['Ticker'])
        old_active = set(old_df[old_df['is_active'] == 1]['Ticker'])

        # Smart updated_date logic
        old_date_df = pd.read_sql("SELECT Ticker, updated_date FROM company_list", conn)
        old_date_dict = dict(zip(old_date_df['Ticker'], old_date_df['updated_date']))

        def get_updated_date(ticker):
            return old_date_dict.get(ticker) or (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

        all_df['updated_date'] = all_df['Ticker'].apply(get_updated_date)
        all_df['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        all_df = all_df.rename(columns={
            'Company name': 'Company',
            'GICs industry group': 'Industry_Group',
            'Listing date': 'listing_date'
        })

        all_df = all_df.sort_values(['is_active', 'Market Cap Num'], ascending=[False, False])

        final_cols = ['Ticker', 'ASX code', 'Company', 'Industry_Group',
                     'Market Cap', 'Market Cap Num', 'listing_date', 
                     'updated_date', 'is_active', 'last_updated']

        master_df = all_df[final_cols].copy()

        # === Change Detection ===
        current_tickers = set(master_df['Ticker'])
        new_tickers = current_tickers - old_set
        dropped_tickers = old_set - current_tickers
        newly_suspended = old_active - set(active_df['Ticker'])

        # Save to DB (full replace for master list - cleanest approach)
        master_df.to_sql('company_list', conn, if_exists='replace', index=False)
        conn.close()

        # Final Summary
        print(f"✅ TOTAL: {len(master_df):,} companies")
        print(f"   Active: {len(active_df):,} | Suspended: {len(suspended_df):,}")
        print(f"   New: {len(new_tickers)} | Dropped: {len(dropped_tickers)} | Newly Suspended: {len(newly_suspended)}")
        if dropped_tickers:
            print(f"   Dropped tickers: {sorted(list(dropped_tickers))[:10]}{'...' if len(dropped_tickers)>10 else ''}")
        if new_tickers:
            print(f"   New tickers (will backfill): {sorted(list(new_tickers))[:8]}...")

        logging.info(f"Updated {len(master_df)} companies | Active: {len(active_df)} | "
                    f"Dropped: {len(dropped_tickers)} | New: {len(new_tickers)}")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Update failed: {e}", exc_info=True)

if __name__ == "__main__":
    init_company_table()
    update_company_list()