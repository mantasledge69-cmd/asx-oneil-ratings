# calculate_oneil_rs_historical.py
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

print("🚀 Calculating Relative RS (tuned for clean chart oscillation)...")

conn = sqlite3.connect('ASX_history.db')
conn.execute("DELETE FROM oneil_rs")

# Load data
df_stocks = pd.read_sql_query("""
    SELECT ticker, date, close 
    FROM price_history 
    WHERE date >= DATE('now', '-420 days')
      AND close > 0
    ORDER BY ticker, date
""", conn)

# ASX 200
df_index = yf.download("^AXJO", start=(datetime.now() - timedelta(days=420)).strftime('%Y-%m-%d'),
                       progress=False, auto_adjust=True)
df_index = df_index[['Close']].reset_index()
df_index['date'] = pd.to_datetime(df_index['Date']).dt.strftime('%Y-%m-%d')
df_index = df_index[['date', 'Close']].rename(columns={'Close': 'close'})

def calc_rs(group, ticker=None):
    group = group.sort_values('date').reset_index(drop=True)
    if len(group) < 252:
        return pd.DataFrame()
    
    rs_records = []
    for i in range(252, len(group)):
        closes = group['close'].iloc[i-252:i+1].values
        current_date = group['date'].iloc[i]
        
        q1 = (closes[-1] / closes[-63] - 1) if len(closes) >= 63 and closes[-63] > 0 else 0
        q2 = (closes[-64] / closes[-126] - 1) if len(closes) >= 126 and closes[-126] > 0 else 0
        q3 = (closes[-127] / closes[-189] - 1) if len(closes) >= 189 and closes[-189] > 0 else 0
        q4 = (closes[-190] / closes[-252] - 1) if len(closes) >= 252 and closes[-252] > 0 else 0
        
        rs_value = 0.4 * q1 + 0.2 * q2 + 0.2 * q3 + 0.2 * q4
        
        rs_records.append({
            'date': current_date,
            'ticker': ticker,
            'rs_value': float(rs_value)
        })
    
    return pd.DataFrame(rs_records)

# Index
index_rs = calc_rs(df_index, '^AXJO')
index_rs = index_rs.rename(columns={'rs_value': 'index_rs'}).drop(columns=['ticker'])

# Stocks
rs_list = [calc_rs(group, ticker) for ticker, group in df_stocks.groupby('ticker')]
rs_df = pd.concat(rs_list, ignore_index=True)

# Relative + Chart column
rs_df = rs_df.merge(index_rs, on='date', how='left')
rs_df['rs_relative'] = rs_df['rs_value'] - rs_df['index_rs']

# Tuned for nice oscillation
rs_df['rs_chart'] = rs_df['rs_relative'].clip(-650, 1100)

rs_df[['date', 'ticker', 'rs_value', 'rs_relative', 'rs_chart']].to_sql('oneil_rs', conn, if_exists='replace', index=False)

print(f"✅ Saved {len(rs_df):,} records")

latest = rs_df[rs_df['date'] == rs_df['date'].max()]
print(f"\nTop 10 on {latest['date'].iloc[0]}:")
print(latest.nlargest(10, 'rs_chart')[['ticker', 'rs_chart', 'rs_relative']])

print(f"Chart range: {latest['rs_chart'].min():.0f} → {latest['rs_chart'].max():.0f}")

conn.close()
print(f"🎉 Done")