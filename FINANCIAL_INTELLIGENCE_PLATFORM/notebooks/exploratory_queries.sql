-- 10 exploratory queries for nifty100.db
-- Q1: Companies per sector
SELECT broad_sector, COUNT(*) AS cnt FROM companies GROUP BY broad_sector ORDER BY cnt DESC;
-- Q2: Avg ROE by sector (latest year)
SELECT c.broad_sector, AVG(fr.return_on_equity_pct) AS avg_roe FROM financial_ratios fr JOIN companies c ON c.company_id=fr.company_id WHERE fr.year='2024' GROUP BY c.broad_sector;
-- Q3: Top 10 by ROE 2024
SELECT c.company_name, fr.return_on_equity_pct FROM financial_ratios fr JOIN companies c ON c.company_id=fr.company_id WHERE fr.year='2024' ORDER BY fr.return_on_equity_pct DESC LIMIT 10;
-- Q4: Debt-free companies 2024
SELECT company_id FROM financial_ratios WHERE year='2024' AND debt_to_equity=0;
-- Q5: Revenue CAGR leaders 5yr
SELECT company_id, revenue_cagr_5yr FROM financial_ratios WHERE year='2024' ORDER BY revenue_cagr_5yr DESC LIMIT 10;
-- Q6: FCF positive streak
SELECT company_id, COUNT(*) AS yrs FROM financial_ratios WHERE free_cash_flow_cr>0 GROUP BY company_id HAVING yrs>=5;
-- Q7: Sector median D/E
SELECT broad_sector, median_de FROM sectors;
-- Q8: Year coverage per company
SELECT company_id, COUNT(*) AS years FROM profitandloss GROUP BY company_id ORDER BY years DESC;
-- Q9: Companies with <5 years
SELECT company_id, COUNT(*) FROM profitandloss GROUP BY company_id HAVING COUNT(*)<5;
-- Q10: FK sanity
SELECT * FROM profitandloss WHERE company_id NOT IN (SELECT company_id FROM companies) LIMIT 5;
