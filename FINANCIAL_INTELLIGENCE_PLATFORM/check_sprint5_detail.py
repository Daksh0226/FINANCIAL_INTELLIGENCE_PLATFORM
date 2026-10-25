import pandas as pd

# Check pros_cons_generated.csv
df = pd.read_csv('output/pros_cons_generated.csv')
print('=== pros_cons_generated.csv ===')
print(f'Rows: {len(df)}')
print(f'Companies with pros: {df[df["type"]=="pro"]["company_id"].nunique()}')
print(f'Companies with cons: {df[df["type"]=="con"]["company_id"].nunique()}')
print(f'Total companies in table: {df["company_id"].nunique()}')
print()
print('Sample:')
print(df[['company_id','type','rule_id','confidence_pct']].head(10).to_string())
print()
print('Confidence distribution:')
print(df['confidence_pct'].describe())

# Check analysis_parsed.csv
df = pd.read_csv('output/analysis_parsed.csv')
print()
print('=== analysis_parsed.csv ===')
print(f'Rows: {len(df)}')
print(df.head())

# Check cashflow_intelligence.xlsx
df = pd.read_excel('output/cashflow_intelligence.xlsx')
print()
print('=== cashflow_intelligence.xlsx ===')
print(f'Rows: {len(df)}')
print(f'Columns: {df.columns.tolist()}')
print(df[['company_id','cfo_quality_label','capex_label','distress_flag','deleveraging_flag','capital_allocation_label']].head(10).to_string())

# Check distress_alerts.csv
df = pd.read_csv('output/distress_alerts.csv')
print()
print('=== distress_alerts.csv ===')
print(f'Rows: {len(df)}')
print(df[['company_id','CFO','CFF','latest_net_profit']].head(10).to_string())