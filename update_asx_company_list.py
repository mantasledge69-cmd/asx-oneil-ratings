import pandas as pd
import sqlite3
import logging
from datetime import datetime

logging.basicConfig(
    filename='update_asx_company_list.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'
DIRECTORY_URL = "https://asx.api.markitdigital.com/asx-research/1.0/companies/directory/file?"

def update_company_list():
    print("🚀 Updating ASX Company Master List...")

    try:
        df = pd.read_csv(DIRECTORY_URL, dtype=str)
        df.columns = [col.strip().replace('"', '').strip() for col in df.columns]

        print(f"Downloaded {len(df):,} total records from ASX")

        # Active filter
        active_mask = (
            ~df['Market Cap'].isin(['SUSPENDED', '--', '', '0', None]) &
            df['Market Cap'].str.replace(',', '', regex=False)
                           .str.replace('.', '', regex=False)
                           .str.isnumeric()
        )

        active_df = df[active_mask].copy()
        suspended_count = len(df) - len(active_df)

        active_df['Market Cap Num'] = pd.to_numeric(
            active_df['Market Cap'].str.replace(',', '', regex=False), errors='coerce'
        )

        active_df = active_df.dropna(subset=['Market Cap Num', 'ASX code']).copy()

        active_df['Ticker'] = active_df['ASX code'] + '.AX'
        active_df['updated_date'] = datetime.now().strftime('%Y-%m-%d')
        active_df['is_active'] = 1

        active_df = active_df.rename(columns={
            'Company name': 'Company',
            'GICs industry group': 'Industry_Group',
            'Listing date': 'listing_date'
        })

        active_df = active_df.sort_values('Market Cap Num', ascending=False).reset_index(drop=True)

        final_cols = ['Ticker', 'ASX code', 'Company', 'Industry_Group',
                     'Market Cap', 'Market Cap Num', 'listing_date', 
                     'updated_date', 'is_active']

        master_df = active_df[final_cols].copy()

        conn = sqlite3.connect(DB_PATH)
        master_df.to_sql('company_list', conn, if_exists='replace', index=False)
        conn.close()

        print(f"✅ SUCCESS: {len(master_df):,} active companies")
        print(f"   Suspended/filtered: {suspended_count}")
        print(f"   Largest: {master_df.iloc[0]['Company']} (${master_df.iloc[0]['Market Cap Num']:,.0f})")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Update failed: {e}")

if __name__ == "__main__":
    update_company_list()