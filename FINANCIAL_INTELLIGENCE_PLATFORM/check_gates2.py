import sqlite3
import pandas as pd

con = sqlite3.connect('data/nifty100.db')

# AC-05: Revenue CAGR spot-check vs Excel
companies = ['TCS', 'RELIANCE', 'HDFCBANK', 'INFY', 'ITC']
placeholders = ','.join(['?'] * len(companies))
df = pd.read_sql('SELECT company_id, year, revenue_cagr_5yr FROM financial_ratios WHERE company_id IN ({}) AND year=2024'.format(placeholders), con, params=companies)
print('AC-05: Revenue CAGR 5yr (2024) spot-check:')
print(df.to_string())

# AC-06: ROE vs companies.roe_percentage within 5% for 5 companies
comp = pd.read_sql('SELECT company_id, roe_percentage FROM companies WHERE company_id IN ({})'.format(placeholders), con, params=companies)
fr = pd.read_sql('SELECT company_id, return_on_equity_pct FROM financial_ratios WHERE company_id IN ({}) AND year=2024'.format(placeholders), con, params=companies)
merged = comp.merge(fr, on='company_id')
merged['diff_pct'] = abs(merged['return_on_equity_pct'] - merged['roe_percentage']) / merged['roe_percentage'] * 100
print()
print('AC-06: ROE vs source roe_percentage:')
print(merged.to_string())

# AC-12: TCS ratios endpoint returns 10+ years
tcs = pd.read_sql('SELECT COUNT(*) as cnt FROM financial_ratios WHERE company_id="TCS"', con)
print()
print('AC-12: TCS ratio years = {} ({})'.format(tcs['cnt'][0], 'PASS' if tcs['cnt'][0] >= 10 else 'FAIL'))

# AC-13: API screener matches screener_output.xlsx
from src.screener.engine import screen
api_qc = screen(preset='Quality Compounder')
xl = pd.read_excel('output/screener_output.xlsx', sheet_name='Quality Compounder')
print('AC-13: API Quality Compounder = {}, Excel = {} ({})'.format(len(api_qc), len(xl), 'PASS' if len(api_qc) == len(xl) else 'FAIL'))

con.close()