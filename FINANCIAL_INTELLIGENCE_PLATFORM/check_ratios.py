import sqlite3
import pandas as pd

con = sqlite3.connect('data/nifty100.db')

# Check financial_ratios columns
df = pd.read_sql('PRAGMA table_info(financial_ratios)', con)
print('=== financial_ratios columns ===')
for _, row in df.iterrows():
    print(f'  {row["name"]} ({row["type"]})')

print()
# Check row count
df = pd.read_sql('SELECT COUNT(*) as cnt FROM financial_ratios', con)
cnt = df.iloc[0]['cnt']
print(f'Row count: {cnt}')

# Check key KPI columns have data
print()
print('=== Key KPI columns non-null counts ===')
key_cols = ['net_profit_margin_pct', 'operating_profit_margin_pct', 'return_on_equity_pct', 
            'return_on_capital_employed_pct', 'return_on_assets_pct', 'debt_to_equity', 
            'interest_coverage', 'asset_turnover', 'free_cash_flow_cr', 'capex_cr',
            'earnings_per_share', 'book_value_per_share', 'dividend_payout_ratio_pct',
            'total_debt_cr', 'cash_from_operations_cr', 'revenue_cagr_5yr', 'pat_cagr_5yr',
            'eps_cagr_5yr', 'composite_quality_score', 'icr_label', 'high_leverage_flag',
            'icr_warning_flag', 'net_debt_cr', 'capex_intensity_pct', 'fcf_conversion_pct',
            'cfo_quality_score', 'cfo_quality_label', 'revenue_cagr_3yr', 'revenue_cagr_10yr',
            'pat_cagr_3yr', 'pat_cagr_10yr', 'eps_cagr_3yr', 'eps_cagr_10yr',
            'fcf_cagr_3yr', 'fcf_cagr_5yr', 'fcf_cagr_10yr',
            'revenue_cagr_5yr_flag', 'pat_cagr_5yr_flag', 'eps_cagr_5yr_flag',
            'fcf_cagr_3yr_flag', 'fcf_cagr_5yr_flag', 'fcf_cagr_10yr_flag',
            'sector_relative_score']

for col in key_cols:
    try:
        df2 = pd.read_sql(f'SELECT COUNT({col}) as cnt FROM financial_ratios WHERE {col} IS NOT NULL', con)
        print(f'  {col}: {df2.iloc[0]["cnt"]} non-null')
    except Exception as e:
        print(f'  {col}: ERROR - {e}')

# Check capital_allocation.csv
print()
print('=== capital_allocation.csv ===')
import os
if os.path.exists('output/capital_allocation.csv'):
    df = pd.read_csv('output/capital_allocation.csv')
    print(f'Rows: {len(df)}')
    print(f'Columns: {df.columns.tolist()}')
    print(df['pattern_label'].value_counts())
else:
    print('NOT FOUND')

# Check ratio_edge_cases.log
print()
print('=== ratio_edge_cases.log ===')
if os.path.exists('output/ratio_edge_cases.log'):
    with open('output/ratio_edge_cases.log', 'r') as f:
        lines = f.readlines()
        print(f'Lines: {len(lines)}')
        for line in lines[:20]:
            print(line.strip())
        if len(lines) > 20:
            print(f'... and {len(lines) - 20} more lines')
else:
    print('NOT FOUND')

con.close()