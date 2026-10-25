import sqlite3
import pandas as pd

con = sqlite3.connect('data/nifty100.db')

print('=== COMPANIES ===')
df = pd.read_sql('SELECT * FROM companies', con)
print(f'Count: {len(df)}')
print(df.head())
print()

print('=== FINANCIAL_RATIOS - check for TTM ===')
df = pd.read_sql("SELECT company_id, year FROM financial_ratios ORDER BY company_id, year", con)
print(f'Total rows: {len(df)}')
print('Years per company (sample):')
print(df.groupby('company_id').agg(list).head(5))
print()

print('=== STOCK_PRICES - check for NULL values ===')
df = pd.read_sql('SELECT * FROM stock_prices', con)
print(f'Total rows: {len(df)}')
print(f'NULL market_cap: {df["market_cap_crore"].isna().sum()}')
print(f'NULL pe_ratio: {df["pe_ratio"].isna().sum()}')
print(f'NULL pb_ratio: {df["pb_ratio"].isna().sum()}')
print(f'NULL dividend_yield: {df["dividend_yield"].isna().sum()}')
print(df.head())
print()

print('=== SECTORS ===')
df = pd.read_sql('SELECT * FROM sectors', con)
print(f'Count: {len(df)}')
print(df)
print()

print('=== PEER_GROUPS ===')
df = pd.read_sql('SELECT * FROM peer_groups', con)
print(f'Count: {len(df)}')
print(df.groupby('peer_group_name').size())
print()

print('=== PEER_PERCENTILES ===')
df = pd.read_sql('SELECT * FROM peer_percentiles', con)
print(f'Count: {len(df)}')
if len(df) > 0:
    print(df.head())
else:
    print('EMPTY - needs to be populated')
print()

print('=== FOREIGN KEY CHECK ===')
cursor = con.cursor()
cursor.execute('PRAGMA foreign_key_check')
fk_issues = cursor.fetchall()
print(f'FK violations: {len(fk_issues)}')
for issue in fk_issues:
    print(f'  {issue}')

con.close()