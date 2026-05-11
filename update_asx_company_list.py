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

def update_company_list():
    print("🚀 Updating ASX Company Master List (Smart updated_date v2)...")
    logging.info("=== Company List Update Started ===")

    try:
        df = pd.read_csv(DIRECTORY_URL, dtype=str)
        df.columns = [col.strip().replace('"', '').strip() for col in df.columns]

        print(f"Downloaded {len(df):,} total records from ASX")

        # Active vs Suspended
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

        # Process Suspended
        suspended_df['Ticker'] = suspended_df['ASX code'] + '.AX'
        suspended_df['is_active'] = 0
        suspended_df['Market Cap Num'] = 0

        all_df = pd.concat([active_df, suspended_df], ignore_index=True)

        # === Smart updated_date Logic ===
        conn = sqlite3.connect(DB_PATH)
        old_df = pd.read_sql("SELECT Ticker, updated_date FROM company_list", conn)
        old_dict = dict(zip(old_df['Ticker'], old_df['updated_date']))

        def get_updated_date(ticker):
            if ticker in old_dict and old_dict[ticker]:
                return old_dict[ticker]
            else:
                # New ticker = 1 year ago for full backfill
                return (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        all_df['updated_date'] = all_df['Ticker'].apply(get_updated_date)

        all_df = all_df.rename(columns={
            'Company name': 'Company',
            'GICs industry group': 'Industry_Group',
            'Listing date': 'listing_date'
        })

        all_df = all_df.sort_values(['is_active', 'Market Cap Num'], ascending=[False, False])

        final_cols = ['Ticker', 'ASX code', 'Company', 'Industry_Group',
                     'Market Cap', 'Market Cap Num', 'listing_date', 
                     'updated_date', 'is_active']

        master_df = all_df[final_cols].copy()

        master_df.to_sql('company_list', conn, if_exists='replace', index=False)
        conn.close()

        print(f"✅ TOTAL: {len(master_df):,} companies")
        print(f"   Active: {len(active_df):,} | Suspended: {len(suspended_df):,}")
        print(f"   New tickers (will backfill 1 year): {len(all_df) - len(old_dict)}")
        print(f"   Largest: {master_df.iloc[0]['Company']} (${master_df.iloc[0]['Market Cap Num']:,.0f})")

        logging.info(f"Updated {len(master_df)} companies | Active: {len(active_df)} | Suspended: {len(suspended_df)}")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Update failed: {e}")

if __name__ == "__main__":
    update_company_list()