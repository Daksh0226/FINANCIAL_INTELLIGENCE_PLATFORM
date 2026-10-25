import sqlite3

con = sqlite3.connect('data/nifty100.db')
cursor = con.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('=== Tables ===')
for t in tables:
    print(t[0])

print()
# Check schema for key tables
for table in ['companies', 'financial_ratios', 'profitandloss', 'balancesheet', 'cashflow', 'stock_prices', 'sectors', 'peer_groups']:
    cursor.execute(f'PRAGMA table_info({table})')
    cols = cursor.fetchall()
    print(f'=== {table} ===')
    for c in cols:
        print(f'  {c[1]} ({c[2]})')
    print()

con.close()