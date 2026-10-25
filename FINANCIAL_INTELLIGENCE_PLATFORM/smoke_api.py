import subprocess
import sys
import time
import requests

proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'src.api.main:app', '--port', '8002'], 
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
try:
    r = requests.get('http://localhost:8002/api/v1/companies')
    print('Companies:', r.status_code, len(r.json().get('companies', [])))
    print('Sample:', r.json().get('companies', [])[:1])
finally:
    proc.terminate()