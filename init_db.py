import sqlite3
DB_PATH = 'ASX_history.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # other tables...
    conn.execute('''CREATE TABLE IF NOT EXISTS oneil_rs (
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        rs_value REAL,
        rs_score REAL,
        rs_rating INTEGER,
        rs_1m REAL, rs_3m REAL, rs_6m REAL, rs_12m REAL,
        rs_relative REAL,
        rs_chart REAL,
        PRIMARY KEY (date, ticker)
    )''')
    conn.commit()
    conn.close()
    print('✅ Database initialized with full oneil_rs schema')

if __name__ == "__main__":
    init_db()