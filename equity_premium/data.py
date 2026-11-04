"""Annual US stock, interest rate, price level and consumption series, 1871 onward, from Robert Shiller.

Source: the workbook for Chapter 26 of Shiller's Market Volatility (1989), updated by Shiller (chapt26.xlsx).
Columns used from its "Data" sheet, with the timing Shiller gives them:
- P: S&P Composite stock price index (Cowles before 1926), January of each year.
- D: dividends accruing to the index over the calendar year.
- R: one-year nominal interest rate, in percent: January and July 6-month prime commercial paper rates
  converted to an annual yield (6-month certificates of deposit after August 1997). It is the return from rolling
  short paper from January of year t to January of t+1.
- CPI: consumer price index, January.
- C: real per capita personal consumption expenditure in 2005 dollars, annual: Kendrick's NBER series to 1929,
  the national accounts (NIPA) after; Shiller's "Consumption" sheet shows the splice.
Not used: E (earnings), RLONG (long bond yield), and the present-value columns.
Shiller's own derived columns RealR and Return are kept only to check the returns rebuilt here.

Data choices:
- The short rate ends in 2011 and consumption in 2009. Shiller's RealR for 2012 treats the missing rate as zero,
  so returns are rebuilt from P, D, R and CPI rather than taken from his columns.
- The 2009 consumption value is for the second quarter only, so it is dropped: consumption growth ends at 2008/2007.
"""
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw" / "chapt26.xlsx"
SERIES = ROOT / "data" / "shiller_annual.csv"
OUTPUT, FIGURES = ROOT / "output", ROOT / "figures"
URL = "http://www.econ.yale.edu/~shiller/data/chapt26.xlsx"

# Position in the Data sheet, the label Shiller puts in header row 3, and the name used here.
COLUMNS = {0: (None, "year"), 1: ("P", "price"), 2: ("D", "dividend"), 4: ("R", "short_rate"), 6: ("CPI", "cpi"),
           7: ("RealR", "shiller_real_rate"), 8: ("C", "consumption"), 15: ("Return", "shiller_return")}


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
    sheet = pd.read_excel(get(URL, RAW), sheet_name="Data", header=None)
    for pos, (label, _) in COLUMNS.items():
        if label is not None and str(sheet.iat[2, pos]).strip() != label:
            raise ValueError(f"column {pos} of the Data sheet is {sheet.iat[2, pos]!r}, expected {label!r}")
    d = sheet[list(COLUMNS)].iloc[8:].apply(pd.to_numeric, errors="coerce")
    d.columns = [name for _, name in COLUMNS.values()]
    d = d[d.year.between(1800, 2100)].astype({"year": int})
    d.loc[d.year == 2009, "consumption"] = np.nan  # second quarter of 2009 only
    d.to_csv(SERIES, index=False)


def load():
    """One row per year t. Returns run from January of t to January of t+1, in real terms (simple, not log).
    Consumption growth for year t is C(t+1)/C(t) - 1, so it lines up with the return over year t
    (beginning-of-period timing); consumption_growth_end is C(t)/C(t-1) - 1, the alternative."""
    d = pd.read_csv(SERIES).sort_values("year").reset_index(drop=True)
    inflation = d.cpi.shift(-1) / d.cpi
    d["stock"] = (d.price.shift(-1) + d.dividend) / d.price / inflation - 1
    d["bill"] = (1 + d.short_rate / 100) / inflation - 1
    d["excess"] = d.stock - d.bill
    d["consumption_growth"] = d.consumption.shift(-1) / d.consumption - 1
    d["consumption_growth_end"] = d.consumption / d.consumption.shift(1) - 1
    return d


if __name__ == "__main__":
    build()
