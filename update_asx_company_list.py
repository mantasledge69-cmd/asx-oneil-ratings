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
            "ASX code" TEXT PRIMARY KEY,
            Company TEXT,
            Industry_Group TEXT,
            "Market Cap" TEXT,
            listing_date TEXT,
            updated_price_date TEXT,
            CSV_updated TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

def update_company_list():
    print("🚀 Updating ASX Company Master List (v30 - Debug Mode)...")
    logging.info("=== Company List Update Started ===")

    try:
        df = pd.read_csv(DIRECTORY_URL, dtype=str, quotechar='"', on_bad_lines='skip')
        df.columns = [col.strip().replace('"', '').strip() for col in df.columns]
        print(f"Downloaded {len(df):,} records from ASX")

        df = df.rename(columns={
            'Company name': 'Company',
            'GICs industry group': 'Industry_Group',
            'Listing date': 'listing_date'
        })

        df['Market Cap'] = df['Market Cap'].astype(str).str.strip()

        # Debug: Show some sample Market Cap values
        print("\nSample Market Cap values:")
        print(df['Market Cap'].head(20).tolist())
        print(df['Market Cap'].tail(10).tolist())

        # Count how many contain SUSPENDED
        susp_count = df['Market Cap'].str.contains(r'SUSPENDED', case=False, na=False).sum()
        print(f"Number of rows with 'SUSPENDED': {susp_count}")

        # Active = anything that is NOT explicitly SUSPENDED
        active_mask = ~df['Market Cap'].str.contains(r'SUSPENDED', case=False, na=False)

        active_df = df[active_mask].copy()
        suspended_df = df[~active_mask].copy()

        print(f"Final Detected → Active: {len(active_df)} | Suspended: {len(suspended_df)}")

        active_df['is_active'] = 1
        suspended_df['is_active'] = 0

        all_df = pd.concat([active_df, suspended_df], ignore_index=True).drop_duplicates(subset=['ASX code'])

        csv_updated = datetime.now().strftime('%d-%m-%Y')

        conn = sqlite3.connect(DB_PATH)
        old_df = pd.read_sql("SELECT * FROM company_list", conn)
        old_set = set(old_df['ASX code'])

        updates = []
        new_companies = []

        for _, row in all_df.iterrows():
            code = row['ASX code']
            old_row = old_df[old_df['ASX code'] == code]

            if not old_row.empty:
                old_active = int(old_row.iloc[0]['is_active'])
                if old_active != int(row['is_active']):
                    updates.append((
                        row['Company'], row['Industry_Group'], row['Market Cap'],
                        row['listing_date'], csv_updated, int(row['is_active']), code
                    ))
            else:
                updated_price_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
                new_companies.append((
                    code, row['Company'], row['Industry_Group'], row['Market Cap'],
                    row['listing_date'], updated_price_date, csv_updated, int(row['is_active'])
                ))

        if updates:
            conn.executemany('''
                UPDATE company_list 
                SET Company=?, Industry_Group=?, "Market Cap"=?, listing_date=?, 
                    CSV_updated=?, is_active=?
                WHERE "ASX code"=?
            ''', updates)

        if new_companies:
            print(f"\n📌 Adding {len(new_companies)} NEW companies to database:")
            for company in new_companies:
                asx_code = company[0]  # First element is "ASX code"
                print(f"   → New: {asx_code}")
            
            conn.executemany('''
                INSERT INTO company_list 
                ("ASX code", Company, Industry_Group, "Market Cap", listing_date, 
                 updated_price_date, CSV_updated, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', new_companies)
            print(f"✅ Successfully inserted {len(new_companies)} new companies.")

        conn.commit()
        conn.close()

        print(f"\n✅ FINAL SUMMARY")
        print(f"   TOTAL in DB: {len(old_df) + len(new_companies)}")
        print(f"   Active: {len(active_df)} | Suspended: {len(suspended_df)}")
        print(f"   New: {len(new_companies)} | Updated: {len(updates)}")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Update failed: {e}", exc_info=True)

if __name__ == "__main__":
    init_company_table()
    update_company_list()