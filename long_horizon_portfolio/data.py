"""Annual US stock returns, dividends and a short rate from Robert Shiller's chapt26.xlsx.

The file has one sheet of data ("Data"), one row per year from 1871, with the column labels in rows 3-8.
Columns used, as the file labels them:
  P       S&P Composite price index, January of the year
  D       dividends accruing to the index during the calendar year
  R       one-year interest rate, percent: six-month commercial paper (six-month CDs from 1997), the January
          and July rates compounded into a one-year return
  CPI     consumer price index, January
  RealR   gross real return on R over the year
  Return  real total return on the index from January to the next January, dividends included
The file has not been updated since 2016: R stops in 2011, D in 2015 and P in January 2016.

Choices:
- The dividend yield at the start of year t is D(t-1) / P(t): last year's dividends over this January's price.
  D(t) itself is not known in January of year t.
- The excess return over year t is ln(1 + Return) - ln(RealR). This equals the nominal log stock return
  minus the nominal log bill return, since both are deflated by the same CPI.
- The file fills RealR for 2012 although R is blank, which amounts to a zero nominal rate. That value is
  dropped, so excess returns run from 1871 to 2011.
"""
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
ANNUAL = ROOT / "data" / "shiller_annual.csv"
OUTPUT, FIGURES = ROOT / "output", ROOT / "figures"
URL = "http://www.econ.yale.edu/~shiller/data/chapt26.xlsx"
COLUMNS = {0: "year", 1: "price", 2: "dividend", 4: "rate", 6: "cpi", 7: "real_rate", 15: "real_return"}


def get(url, path):
    """Download once into data/raw; later runs read the cached file."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=120) as r:
                    path.write_bytes(r.read())
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
    return path


def build():
    d = pd.read_excel(get(URL, RAW / "chapt26.xlsx"), sheet_name="Data", header=None, skiprows=8,
                      usecols=list(COLUMNS)).rename(columns=COLUMNS)
    d = d[pd.to_numeric(d.year, errors="coerce").notna()].astype(float)  # notes below the table have no year
    d["year"] = d.year.astype(int)
    d.loc[d.rate.isna(), "real_rate"] = np.nan
    d["dividend_yield"] = d.dividend.shift(1) / d.price
    d["log_dp"] = np.log(d.dividend_yield)
    d["log_excess"] = np.log1p(d.real_return) - np.log(d.real_rate)
    d.to_csv(ANNUAL, index=False)


def load():
    return pd.read_csv(ANNUAL)


if __name__ == "__main__":
    build()
