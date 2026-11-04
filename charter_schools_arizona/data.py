"""School-level panel for Arizona and New Mexico, 1990-91 to 2005-06, and county youth population shares.

Schools: NCES Common Core of Data through the Urban Institute Education Data API (no key).
County population: US Census Bureau intercensal county estimates by age, race and Hispanic origin.
A year is the fall of the school year: 1994 is 1994-95.
"""
import io
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
PANEL = ROOT / "data" / "panel.csv.gz"
COUNTY = ROOT / "data" / "county_youth.csv"
OUTPUT, FIGURES = ROOT / "output", ROOT / "figures"

STATES = {4: "AZ", 35: "NM"}
YEARS = range(1990, 2006)
API = "https://educationdata.urban.org/api/v1/schools/ccd"
WHITE, TOTAL = 1, 99  # Urban's race codes: 1 is white (Hispanic is its own code), 99 is all students
DIRECTORY = ["ncessch", "year", "fips", "leaid", "school_type", "charter", "teachers_fte", "enrollment",
             "lowest_grade_offered", "urban_centric_locale", "county_code"]
CENSUS_90S = "https://www2.census.gov/programs-surveys/popest/tables/1990-2000/intercensal/st-co/stch-icen{year}.txt"
CENSUS_00S = "https://www2.census.gov/programs-surveys/popest/datasets/2000-2010/intercensal/county/co-est00int-alldata-{fips:02d}.csv"


def get(url, path):
    """Download once into data/raw; later runs read the cached file."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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


def api(endpoint, year, fips):
    """All rows of one endpoint ("directory" or "enrollment/{year}/grade-99/race"), year and state, page by page."""
    path = endpoint.format(year=year) if "{year}" in endpoint else f"{endpoint}/{year}"
    url, rows, page = f"{API}/{path}/?fips={fips}", [], 0
    while url:
        name = f"{endpoint.split('/')[0]}_{year}_{fips}_{page}.json"
        d = json.loads(get(url, RAW / name))
        rows += d["results"]
        url, page = d.get("next"), page + 1
    return rows


def schools():
    """One row per school and year: enrolment, white non-Hispanic students, teachers and descriptors."""
    frames = []
    for fips in STATES:
        for year in YEARS:
            directory = pd.DataFrame(api("directory", year, fips))[DIRECTORY]
            race = pd.DataFrame(api("enrollment/{year}/grade-99/race", year, fips))
            race = race[race.sex == TOTAL] if "sex" in race else race
            counts = race.pivot_table(index="ncessch", columns="race", values="enrollment", aggfunc="sum")
            directory = directory.merge(counts[[WHITE, TOTAL]].rename(columns={WHITE: "white", TOTAL: "students"}),
                                        left_on="ncessch", right_index=True, how="left")
            frames.append(directory)
    d = pd.concat(frames, ignore_index=True)
    d["state"] = d.fips.map(STATES)
    # The county code is filled only in later years of the files; a school keeps its county.
    code = pd.to_numeric(d.county_code, errors="coerce")
    d["county"] = code.where(code > 0)
    d["county"] = d.groupby("ncessch").county.transform(lambda s: s.dropna().mode().iloc[0] if s.notna().any() else pd.NA)
    return d.drop(columns="county_code")


def county_youth():
    """Share of 5- to 19-year-olds who are white non-Hispanic, by county and July 1 of each year."""
    rows = []
    for year in range(1990, 2000):  # columns: year, county FIPS, age group, race-sex, Hispanic origin, population
        text = get(CENSUS_90S.format(year=year), RAW / f"stch-icen{year}.txt").decode()
        d = pd.read_csv(io.StringIO(text), sep=r"\s+", header=None, names=["yy", "county", "age", "racesex", "hisp", "pop"])
        d = d[(d.county // 1000).isin(list(STATES)) & d.age.between(2, 4)]  # 5-9, 10-14, 15-19
        white = d[d.racesex.isin((1, 2)) & (d.hisp == 1)].groupby("county")["pop"].sum()
        rows.append(pd.DataFrame({"year": year, "youth_white": white, "youth": d.groupby("county")["pop"].sum()}))
    for fips in STATES:  # YEAR 3 is July 1 2001 ... 8 is July 1 2006 (2 is July 1 2000)
        d = pd.read_csv(io.BytesIO(get(CENSUS_00S.format(fips=fips), RAW / f"co-est00int-alldata-{fips:02d}.csv")),
                        encoding="latin-1")
        d = d[d.YEAR.between(2, 7) & d.AGEGRP.between(2, 4)]
        d["county"] = d.STATE * 1000 + d.COUNTY
        g = d.groupby(["YEAR", "county"])
        part = pd.DataFrame({"youth_white": g.NHWA_MALE.sum() + g.NHWA_FEMALE.sum(), "youth": g.TOT_POP.sum()}).reset_index()
        part["year"] = part.YEAR + 1998
        rows.append(part.drop(columns="YEAR").set_index("county"))
    c = pd.concat(rows).reset_index()
    c["youth_white_share"] = c.youth_white / c.youth
    return c[["county", "year", "youth_white_share"]].sort_values(["county", "year"])


def build():
    d = schools()
    d.to_csv(PANEL, index=False)
    county_youth().to_csv(COUNTY, index=False)


def load():
    d = pd.read_csv(PANEL, dtype={"ncessch": str, "leaid": str})
    c = pd.read_csv(COUNTY)
    return d.merge(c, on=["county", "year"], how="left")


if __name__ == "__main__":
    build()
