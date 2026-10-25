import os
import glob

# Check dashboard files
print('=== Dashboard files ===')
for f in ['src/dashboard/app.py', 'src/dashboard/utils/db.py', 'src/dashboard/utils/theme.py']:
    status = "EXISTS" if os.path.exists(f) else "MISSING"
    print(f'  {f}: {status}')

print()
print('=== Pages ===')
for i in range(1, 9):
    f = f'src/dashboard/pages/0{i}_*.py'
    files = glob.glob(f)
    status = "EXISTS" if files else "MISSING"
    print(f'  Page {i}: {status} - {files[0] if files else ""}')

print()
# Check valuation
print('=== Valuation files ===')
for f in ['src/analytics/valuation.py', 'output/valuation_summary.xlsx', 'output/valuation_flags.csv']:
    status = "EXISTS" if os.path.exists(f) else "MISSING"
    print(f'  {f}: {status}')