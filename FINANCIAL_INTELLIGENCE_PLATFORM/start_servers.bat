@echo off
cd /d "%~dp0"

echo ========================================
echo Financial Intelligence Platform
echo ========================================
echo.
echo Dashboard: http://localhost:8501
echo API Docs:  http://localhost:8000/docs
echo.
echo Press Ctrl+C in EACH window to stop servers
echo.

:: Open Dashboard in new window
start "Dashboard (port 8501)" cmd /k "cd /d "%~dp0" && streamlit run src/dashboard/app.py --server.port 8501 --server.address 0.0.0.0"

:: Open API in new window  
start "API (port 8000)" cmd /k "cd /d "%~dp0" && uvicorn src.api.main:app --port 8000 --reload"

echo Both server windows opened.
echo Close them or press Ctrl+C in each to stop.
pause