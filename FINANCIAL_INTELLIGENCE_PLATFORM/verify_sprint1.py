import sqlite3

con = sqlite3.connect('data/nifty100.db')
cursor = con.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('=== Tables in nifty100.db ===')
for t in tables:
    print(f'  {t[0]}')

# Verify row counts
print()
print('=== Row counts ===')
for table in ['companies', 'profitandloss', 'balancesheet', 'cashflow', 'analysis', 'documents', 'prosandcons', 'sectors', 'stock_prices', 'financial_ratios', 'peer_groups', 'peer_percentiles']:
    cursor.execute(f'SELECT COUNT(*) FROM {table}')
    count = cursor.fetchone()[0]
    print(f'  {table}: {count}')

# FK check
cursor.execute('PRAGMA foreign_key_check')
fk = cursor.fetchall()
print(f'\n=== FK violations: {len(fk)} ===')
for f in fk:
    print(f'  {f}')

con.close()