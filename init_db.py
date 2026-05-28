import sqlite3
import logging
from datetime import datetime
import os

# Logging setup - per file as per project requirement
logging.basicConfig(
    filename='init_db.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DB_PATH = 'ASX_history.db'
DATA_DIR = 'data'
PKL_DIR = os.path.join(DATA_DIR, 'pkl')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PKL_DIR, exist_ok=True)

def init_db():
    """Initialize the complete SQLite database structure for ASX Oneil Ratings project.
    
    Tables:
    - company_list: Master list of ASX companies (from existing update script)
    - price_history: Daily close prices (from yfinance, cached via pkl for efficiency)
    - oneil_ratings: O'Neil Proprietary Ratings (1-99 scale, components for EPS, RS, etc.)
    - sector_performance: Daily/periodic sector aggregates for outperformance analysis
    - gs_momentum: GS High Beta Momentum Long Index scores per stock
    - update_logs: Optional audit table for runs
    
    Indexes added for query performance on large datasets.
    """
    logging.info("=== init_db.py: Starting full database initialization ===")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. company_list - matches existing update_asx_company_list.py exactly
    cursor.execute('''
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
    logging.info("Table 'company_list' ensured (matches production script)")
    
    # 2. price_history - daily closes, with pkl cache support
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            "ASX code" TEXT NOT NULL,
            close REAL NOT NULL,
            volume INTEGER,
            UNIQUE(date, "ASX code")
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_code_date ON price_history("ASX code", date)')
    logging.info("Table 'price_history' created with index for fast lookups")
    
    # 3. oneil_ratings - O'Neil Proprietary Rating & Rankings (see williamoneil.com for methodology)
    # Rating = weighted composite (EPS Growth, RS, Sales, Profit Margin, etc.) 1-99
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oneil_ratings (
            "ASX code" TEXT PRIMARY KEY,
            rating INTEGER CHECK(rating BETWEEN 1 AND 99),
            eps_rating INTEGER,
            relative_strength_rating INTEGER,
            sales_growth_rating INTEGER,
            profit_margin_rating INTEGER,
            institutional_ownership_rating INTEGER,
            industry_group_rank INTEGER,
            last_updated TEXT,
            notes TEXT
        )
    ''')
    logging.info("Table 'oneil_ratings' created for O'Neil 1-99 proprietary scores")
    
    # 4. sector_performance - for quick sector outperformance views (1d, 5d, 20d, YTD)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sector_performance (
            date TEXT NOT NULL,
            industry_group TEXT NOT NULL,
            avg_1d_change REAL,
            avg_5d_change REAL,
            avg_20d_change REAL,
            avg_ytd_change REAL,
            num_active_stocks INTEGER,
            top_stock_code TEXT,
            top_stock_return REAL,
            PRIMARY KEY (date, industry_group)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sector_perf_date ON sector_performance(date)')
    logging.info("Table 'sector_performance' created for sector heatmaps & rankings")
    
    # 5. gs_momentum - GS High Beta Momentum Long Index components
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gs_momentum (
            "ASX code" TEXT NOT NULL,
            date TEXT NOT NULL,
            beta REAL,
            momentum_20d REAL,
            momentum_60d REAL,
            volume_surge REAL,
            composite_score REAL,
            rank INTEGER,
            PRIMARY KEY ("ASX code", date)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_gs_momentum_score ON gs_momentum(composite_score DESC)')
    logging.info("Table 'gs_momentum' created for High Beta Momentum Long analysis")
    
    # 6. update_logs - audit trail for all backend runs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS update_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_name TEXT,
            run_date TEXT,
            status TEXT,
            records_processed INTEGER,
            error_message TEXT
        )
    ''')
    logging.info("Table 'update_logs' created for debugging & audit")
    
    conn.commit()
    conn.close()
    
    logging.info("=== init_db.py: Database initialization COMPLETE. All tables ready for ASX Oneil project ===")
    print("✅ ASX_history.db initialized with full schema (company_list + price_history + oneil_ratings + sector_performance + gs_momentum + update_logs)")
    print("   pkl cache directory ready at data/pkl/ for Yahoo Finance daily close caching")

if __name__ == "__main__":
    init_db()