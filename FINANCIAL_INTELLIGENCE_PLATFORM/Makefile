.PHONY: load ratios test report dashboard api clean

load:
	python -m src.etl.loader

ratios:
	python -m src.analytics.ratios
	python -m src.analytics.cagr
	python -m src.analytics.cashflow_kpis

test:
	pytest tests/ -v --html=reports/pytest_report.html --self-contained-html

report:
	python -m src.reports.tearsheet
	python -m src.reports.sector_report

dashboard:
	streamlit run src/dashboard/app.py --server.port 8501

api:
	uvicorn src.api.main:app --port 8000 --reload

clean:
	python -c "import pathlib,shutil; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]; [shutil.rmtree(str(p),ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
