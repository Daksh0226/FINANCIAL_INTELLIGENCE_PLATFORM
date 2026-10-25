import sqlite3
import pandas as pd

con = sqlite3.connect('data/nifty100.db')

# Check peer_percentiles table
df = pd.read_sql('SELECT COUNT(*) as cnt FROM peer_percentiles', con)
cnt = df.iloc[0]['cnt']
print(f'peer_percentiles rows: {cnt}')

# Spot check IT Services ROE ranking
df = pd.read_sql('''
    SELECT pp.company_id, c.company_name, pp.metric, pp.value, pp.percentile_rank
    FROM peer_percentiles pp
    JOIN companies c ON pp.company_id = c.company_id
    WHERE pp.peer_group_name = 'IT Services' AND pp.metric = 'return_on_equity_pct'
    ORDER BY pp.percentile_rank DESC
''', con)
print()
print('=== IT Services ROE ranking ===')
print(df.to_string())

# Spot check FMCG ROE ranking
df = pd.read_sql('''
    SELECT pp.company_id, c.company_name, pp.metric, pp.value, pp.percentile_rank
    FROM peer_percentiles pp
    JOIN companies c ON pp.company_id = c.company_id
    WHERE pp.peer_group_name = 'FMCG' AND pp.metric = 'return_on_equity_pct'
    ORDER BY pp.percentile_rank DESC
''', con)
print()
print('=== FMCG ROE ranking ===')
print(df.to_string())

# Verify D/E is inverted (lower = better = higher percentile)
df = pd.read_sql('''
    SELECT pp.company_id, c.company_name, pp.metric, pp.value, pp.percentile_rank
    FROM peer_percentiles pp
    JOIN companies c ON pp.company_id = c.company_id
    WHERE pp.peer_group_name = 'IT Services' AND pp.metric = 'debt_to_equity'
    ORDER BY pp.percentile_rank DESC
''', con)
print()
print('=== IT Services D/E ranking (should be inverted: lower D/E = higher percentile) ===')
print(df.to_string())

con.close()