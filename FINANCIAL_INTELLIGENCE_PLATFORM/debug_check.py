import sqlite3
import pandas as pd

con = sqlite3.connect('data/nifty100.db')

# Check TTM data for ABB
fr = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id='ABB' AND year='TTM'", con)
print('TTM data for ABB:')
if not fr.empty:
    print(fr[['company_id','year','return_on_equity_pct','debt_to_equity','free_cash_flow_cr','revenue_cagr_5yr','pat_cagr_5yr','composite_quality_score']].T.to_string())
else:
    print('No TTM data')

# Check 2024 data
fr = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id='ABB' AND year='2024'", con)
print()
print('2024 data for ABB:')
if not fr.empty:
    print(fr[['company_id','year','return_on_equity_pct','debt_to_equity','free_cash_flow_cr','revenue_cagr_5yr','pat_cagr_5yr','composite_quality_score']].T.to_string())
else:
    print('No 2024 data')

con.close()