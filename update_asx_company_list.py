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
    print("🚀 Daily ASX Company List Update Started...")
    logging.info("=== Daily Company List Update Started ===")

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

        active_df['Market Cap Num'] = pd.to_numeric(
            active_df['Market Cap'].str.replace(',', '', regex=False), errors='coerce'
        )
        active_df = active_df.dropna(subset=['Market Cap Num', 'ASX code']).copy()

        active_df['Ticker'] = active_df['ASX code'] + '.AX'
        active_df['is_active'] = 1

        suspended_df['Ticker'] = suspended_df['ASX code'] + '.AX'
        suspended_df['is_active'] = 0
        suspended_df['Market Cap Num'] = 0

        all_df = pd.concat([active_df, suspended_df], ignore_index=True)
        all_df['updated_date'] = datetime.now().strftime('%Y-%m-%d')

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

        # === Change Detection ===
        conn = sqlite3.connect(DB_PATH)
        old_df = pd.read_sql("SELECT Ticker, is_active FROM company_list", conn)

        old_tickers = set(old_df['Ticker'])
        new_tickers = set(master_df['Ticker']) - old_tickers

        # Status changes
        current_status = master_df.set_index('Ticker')['is_active']
        if not old_df.empty:
            old_status = old_df.set_index('Ticker')['is_active']
            status_changes = current_status.compare(old_status, keep_equal=False)

        # Save
        master_df.to_sql('company_list', conn, if_exists='replace', index=False)
        conn.close()

        # === Smart Logging ===
        print(f"✅ Updated: {len(master_df):,} total companies")
        print(f"   Active: {len(active_df):,} | Suspended: {len(suspended_df):,}")

        if new_tickers:
            print(f"🆕 New tickers added: {len(new_tickers)}")
            logging.info(f"NEW TICKERS: {sorted(list(new_tickers))[:20]}")

        if 'status_changes' in locals() and not status_changes.empty:
            suspended = status_changes[status_changes['self'] == 0].index.tolist()
            reactivated = status_changes[status_changes['self'] == 1].index.tolist()
            if suspended:
                print(f"⛔ Suspended: {len(suspended)}")
                logging.warning(f"SUSPENDED: {suspended[:10]}")
            if reactivated:
                print(f"✅ Reactivated: {len(reactivated)}")
                logging.info(f"REACTIVATED: {reactivated[:10]}")

        print(f"   Largest: {master_df.iloc[0]['Company']} (${master_df.iloc[0]['Market Cap Num']:,.0f})")
        logging.info(f"Daily update completed - Active: {len(active_df)} | Suspended: {len(suspended_df)}")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Update failed: {e}")

if __name__ == "__main__":
    update_company_list()