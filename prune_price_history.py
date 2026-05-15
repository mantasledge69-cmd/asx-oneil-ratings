# prune_price_history.py
import sqlite3
from datetime import datetime

print("🗑️  Pruning price_history to last 2 years only...")

conn = sqlite3.connect('ASX_history.db')
cur = conn.cursor()

cur.execute("""
    DELETE FROM price_history 
    WHERE date < DATE('now', '-730 days')
""")
deleted = cur.rowcount
conn.commit()

# Stats
cur.execute("""
    SELECT COUNT(*) as rows, 
           MIN(date) as oldest, 
           MAX(date) as newest 
    FROM price_history
""")
stats = cur.fetchone()

print(f"✅ Deleted {deleted:,} old records")
print(f"Remaining rows : {stats[0]:,}")
print(f"Date range     : {stats[1]} → {stats[2]}")

conn.close()
print(f"Prune completed at {datetime.now().strftime('%Y-%m-%d %H:%M')}")