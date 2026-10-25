import re
import pandas as pd

# Canonical ticker aliases: source variant -> canonical company_id used in db/schema.sql.
#
# AGTL is a typo present only in data/source/cashflow.xlsx (7 rows). Every other
# canonical source -- companies, sectors, profitandloss, balancesheet, documents,
# market_cap, stock_prices -- uses ATGL for Adani Total Gas Ltd, so ATGL is the
# canonical id. Mapping it here keeps the source workbook untouched while giving
# the whole pipeline a single company identity.
TICKER_ALIASES = {
    "AGTL": "ATGL",
}

def normalize_year(value) -> str | None:
    """Normalize year to YYYY or YYYY-MM format. Returns None if unparseable."""
    if pd.isna(value):
        return None
    s = str(value).strip()
    # 2020-21, 2020/21, 2020-2021 must be before YYYY-MM (2020-21 looks like YYYY-MM but is a range)
    m = re.match(r"^(\d{4})[\-/]\d{2,4}$", s)
    if m:
        # if second part is 01-12 and first check would be month-like, still treat as range if the string is like 2020-21 (year range)
        # Distinguish: 2020-06 is YYYY-MM, 2020-21 is year range. We treat 00-31 as month only if <=12
        parts = re.split(r"[\-/]", s)
        if len(parts)==2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 12 and len(parts[1])==2:
            # Could be both; prefer YYYY-MM only if s matches YYYY-MM and second part <=12 and we want to keep it
            # But test expects 2020-21 -> 2020, so 21 >12 => range
            pass
        # if second part >12 or len 4, it's a range -> return first year
        if len(parts)==2:
            try:
                if int(parts[1]) > 12 or len(parts[1])==4:
                    return m.group(1)
            except:
                pass
    # Already YYYY-MM (valid month 01-12)
    if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", s):
        return s
    # YYYY
    if re.match(r"^\d{4}$", s):
        return s
    # FY2020, FY 2020, FY-2020
    m = re.match(r"(?i)fy[\s\-]*(\d{4})", s)
    if m:
        return m.group(1)
    # 2020-21, 2020/21, 2020-2021 (general)
    m = re.match(r"(\d{4})[\-/]\d{2,4}", s)
    if m:
        return m.group(1)
    # Mar 2020, March 2020, Mar-2020, Mar-13 (2-digit year)
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-]+(\d{2,4})", s, re.I)
    if m:
        y = m.group(2)
        if len(y) == 2:
            # 00-30 -> 2000-2030, 31-99 -> 1931-1999
            yy = int(y)
            return f"20{yy:02d}" if yy <= 30 else f"19{yy:02d}"
        return y
    # 2020.0 float string
    m = re.match(r"(\d{4})\.0$", s)
    if m:
        return m.group(1)
    # Extract 4-digit year anywhere
    m = re.search(r"(19|20)\d{2}", s)
    if m:
        return m.group(0)
    return None

def normalize_ticker(value) -> str | None:
    """Trim spaces, uppercase, remove special chars except hyphen, then apply canonical aliases."""
    if pd.isna(value):
        return None
    s = str(value).strip().upper()
    if not s or s == "NAN":
        return None
    # Remove spaces inside
    s = re.sub(r"\s+", "", s)
    # Keep alphanumeric, -, _, .
    s = re.sub(r"[^A-Z0-9\-_\.]", "", s)
    if not s:
        return None
    return TICKER_ALIASES.get(s, s)

def normalize_company_id(value) -> str | None:
    return normalize_ticker(value)
