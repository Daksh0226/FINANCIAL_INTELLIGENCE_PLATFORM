import os
import glob

print('=== NLP Files ===')
for f in ['src/nlp/parser.py', 'src/nlp/pros_cons_generator.py']:
    status = "EXISTS" if os.path.exists(f) else "MISSING"
    print(f'  {f}: {status}')

print()
print('=== Reports Files ===')
for f in ['src/reports/tearsheet.py', 'src/reports/sector_report.py']:
    status = "EXISTS" if os.path.exists(f) else "MISSING"
    print(f'  {f}: {status}')

print()
print('=== NLP Output ===')
for f in ['output/pros_cons_generated.csv', 'output/analysis_parsed.csv', 'output/parse_failures.csv']:
    status = "EXISTS" if os.path.exists(f) else "MISSING"
    size = os.path.getsize(f) if os.path.exists(f) else 0
    print(f'  {f}: {status} ({size} bytes)')

print()
print('=== Cash Flow Intelligence ===')
for f in ['output/cashflow_intelligence.xlsx', 'output/distress_alerts.csv', 'output/pattern_changes.csv']:
    status = "EXISTS" if os.path.exists(f) else "MISSING"
    size = os.path.getsize(f) if os.path.exists(f) else 0
    print(f'  {f}: {status} ({size} bytes)')

print()
print('=== PDF Reports ===')
tearsheets = glob.glob('reports/tearsheets/*.pdf')
sectors = glob.glob('reports/sector/*.pdf')
portfolio = glob.glob('reports/portfolio/*.pdf')
print(f'  Tearsheets: {len(tearsheets)} PDFs')
print(f'  Sector reports: {len(sectors)} PDFs')
print(f'  Portfolio: {len(portfolio)} PDFs')

if tearsheets:
    sizes = [os.path.getsize(f) for f in tearsheets]
    print(f'  Tearsheet sizes: min={min(sizes)//1024}KB, max={max(sizes)//1024}KB, avg={sum(sizes)//len(sizes)//1024}KB')