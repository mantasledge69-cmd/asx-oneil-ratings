import pandas as pd
import sqlite3
import logging
from datetime import datetime

logging.basicConfig(filename='update_asx_company_list.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DB_PATH = 'ASX_history.db'
DIRECTORY_URL = "https://asx.api.markitdigital.com/asx-research/1.0/companies/directory/file?"

def update_company_list():
    print("🚀 Updating ASX Company Master List...")

    try:
        df = pd.read_csv(DIRECTORY_URL, dtype=str)

        # Clean columns
        df.columns = [col.strip().replace('"', '').strip() for col in df.columns]

        # Filter active companies
        active_mask = (
            ~df['Market Cap'].isin(['SUSPENDED', '--', '', '0']) &
            df['Market Cap'].str.replace(',', '', regex=False)
                           .str.replace('.', '', regex=False)
                           .str.isnumeric()
        )

        active_df = df[active_mask].copy()
        suspended = len(df) - len(active_df)

        active_df['Market Cap Num'] = pd.to_numeric(
            active_df['Market Cap'].str.replace(',', '', regex=False), errors='coerce'
        )

        active_df = active_df.dropna(subset=['Market Cap Num', 'ASX code'])

        active_df['Ticker'] = active_df['ASX code'] + '.AX'
        active_df['updated_date'] = datetime.now().strftime('%Y-%m-%d')
        active_df['is_active'] = 1

        # Rename for our schema
        master_df = active_df.rename(columns={
            'Company name': 'Company',
            'GICs industry group': 'Industry_Group'
        })

        final_cols = ['Ticker', 'ASX code', 'Company', 'Industry_Group',
                     'Market Cap', 'Market Cap Num', 'updated_date', 'is_active']

        master_df = master_df[final_cols]

        # Save to DB
        conn = sqlite3.connect(DB_PATH)
        master_df.to_sql('company_list', conn, if_exists='replace', index=False)
        conn.close()

        print(f"✅ Company list updated: {len(master_df):,} active companies")
        print(f"   Suspended/filtered: {suspended}")
        print(f"   Largest: {master_df.iloc[0]['Company']} (${master_df.iloc[0]['Market Cap Num']:,.0f})")

        logging.info(f"Updated {len(master_df)} active companies")

    except Exception as e:
        print(f"❌ Error updating company list: {e}")
        logging.error(f"Failed: {e}")

if __name__ == "__main__":
    update_company_list()
