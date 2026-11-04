"""Quarterly Canadian series for the model comparison, from Statistics Canada.

Output, consumption and investment: table 36-10-0104, GDP by expenditure, seasonally adjusted at annual rates.
Labour and capital income: table 36-10-0103, GDP by income, seasonally adjusted at annual rates.
Hours: Labour Force Survey table 14-10-0289, total actual hours worked at main job, monthly, seasonally adjusted.
Population aged 15 to 64: Labour Force Survey table 14-10-0287, through Statistics Canada's web data service.
Capital: National Balance Sheet Accounts, table 36-10-0580, market value at the end of each quarter, from 1990.
"""
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
QUARTERLY = ROOT / "data" / "quarterly.csv"
OUTPUT, FIGURES = ROOT / "output", ROOT / "figures"

TABLE = "https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip"
WDS = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromCubePidCoordAndLatestNPeriods"
# Canada; population; all genders; 15 to 64 years; estimate; seasonally adjusted (member ids from the table's metadata)
POPULATION = {"productId": 14100287, "coordinate": "1.1.1.8.1.1.0.0.0.0", "latestN": 2000}

GDP = "Gross domestic product at market prices"
FINAL = "Final consumption expenditure"
DURABLES = "Durable goods"
GOV_C = "General governments final consumption expenditure"
GFCF = "Gross fixed capital formation"
GOV_I = "General governments gross fixed capital formation"
INVENTORIES = "Investment in inventories"
HOURS = "Total actual hours worked, all industries"
CAPITAL = "Produced non-financial assets"  # fixed assets, inventories and consumer durables


def get(url, path, body=None):
    """Download once into data/raw; later runs read the cached file. A body makes it a JSON POST."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
        request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=300) as r:
                    path.write_bytes(r.read())
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
    return path.read_bytes()


def table(pid, keep=None):
    """A full-table CSV. keep filters it chunk by chunk (the balance sheet file is 190 MB unzipped)."""
    raw = get(TABLE.format(pid=pid), RAW / f"{pid}-eng.zip")
    with zipfile.ZipFile(io.BytesIO(raw)) as z, z.open(f"{pid}.csv") as f:
        if keep is None:
            return pd.read_csv(f, dtype={"TERMINATED": str})
        return pd.concat([keep(c) for c in pd.read_csv(f, dtype={"TERMINATED": str}, chunksize=500_000)])


def to_quarters(monthly):
    """Average of the three months in each quarter; a quarter with a missing month is dropped."""
    g = monthly.groupby(pd.PeriodIndex(monthly.index, freq="M").asfreq("Q"))
    return g.mean()[g.count() == 3]


def expenditure():
    """Output, consumption (non-durables and services, excluding government) and investment (business and
    non-profit fixed investment, durables and inventories), in chained dollars and in current prices."""
    d = table(36100104)
    d = d[d.TERMINATED.isna() & (d["Seasonal adjustment"] == "Seasonally adjusted at annual rates")]
    real = d[d.Prices.str.fullmatch(r"Chained \(\d{4}\) dollars")]
    if real.Prices.nunique() != 1:
        raise ValueError(f"expected one chained base, found {real.Prices.unique()}")
    out = []
    for prices, suffix in ((real, ""), (d[d.Prices == "Current prices"], "_nominal")):
        t = prices.pivot(index="REF_DATE", columns="Estimates", values="VALUE")
        out.append(pd.DataFrame({"Y": t[GDP], "C": t[FINAL] - t[DURABLES] - t[GOV_C],
                                 "I": t[GFCF] + t[DURABLES] + t[INVENTORIES] - t[GOV_I]}).add_suffix(suffix))
    return pd.concat(out, axis=1)


def income():
    """Compensation of employees and gross operating surplus, the unambiguous parts of labour and capital income."""
    d = table(36100103)
    d = d[d.TERMINATED.isna() & (d["Seasonal adjustment"] == "Seasonally adjusted at annual rates")]
    t = d.pivot(index="REF_DATE", columns="Estimates", values="VALUE")
    return pd.DataFrame({"compensation": t["Compensation of employees"], "operating_surplus": t["Gross operating surplus"]})


def hours():
    """Thousands of hours actually worked at main jobs in the survey reference week, quarterly average."""
    d = table(14100289)
    d = d[(d["North American Industry Classification System (NAICS)"] == HOURS) & (d.Statistics == "Estimate")]
    return to_quarters(d.set_index("REF_DATE").VALUE).rename("H")


def population():
    """Thousands of people aged 15 to 64, quarterly average."""
    d = json.loads(get(WDS, RAW / "population_15_64.json", [POPULATION]))[0]["object"]["vectorDataPoint"]
    s = pd.Series({p["refPer"][:7]: p["value"] for p in d})
    return to_quarters(s).rename("population")


def capital():
    """Produced capital of every sector except general governments, at market value, millions of dollars."""
    keep = lambda c: c[(c.Valuation == "Market value") & (c.Categories == CAPITAL)
                       & c.Sectors.isin(["National balance sheets", "General governments"])]
    t = table(36100580, keep).pivot(index="REF_DATE", columns="Sectors", values="VALUE")
    return (t["National balance sheets"] - t["General governments"]).rename("K_nominal")


def build():
    parts = [expenditure(), income(), capital()]
    for p in parts:
        p.index = pd.PeriodIndex(p.index, freq="Q")
    d = pd.concat(parts + [hours(), population()], axis=1).sort_index()
    d.index.name = "quarter"
    d.to_csv(QUARTERLY)


def load():
    d = pd.read_csv(QUARTERLY, index_col="quarter")
    d.index = pd.PeriodIndex(d.index, freq="Q")
    return d


if __name__ == "__main__":
    build()
