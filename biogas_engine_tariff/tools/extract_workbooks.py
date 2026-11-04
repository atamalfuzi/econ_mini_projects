"""One-off: read the mapped cells of the two business-plan workbooks into data/workbook_cells.csv.

Usage, from this folder (needs xlrd, which is not in requirements.txt):
    .venv/Scripts/pip install xlrd==2.0.2
    .venv/Scripts/python tools/extract_workbooks.py path/to/CNG.xls path/to/Bio.xls

Both workbooks use the same template. Only the first sheet, '90% تبریز' ("90% Tabriz"), is the plan for this
538.3 kW plant. The second sheet is an earlier 1 MW plan by another author and is not used.
"""
import csv
import sys
from pathlib import Path

import xlrd

SHEET = 0
CELLS = [  # cell, item (English), unit
    ("D36", "rated output", "kW (text)"),
    ("E36", "annual output", "kWh"),
    ("G36", "tariff used in the workbook", "rials/kWh"),
    ("E145", "fuel use", "m3/h"),
    ("G145", "fuel price (gas) or upgrading cost (biogas)", "rials/m3"),
    ("I145", "fuel cost, one hour", "rials"),
    ("I174", "land", "rials"),
    ("I175", "site preparation", "rials"),
    ("I176", "building", "rials"),
    ("I106", "engine", "rials"),
    ("I108", "biogas compressor", "rials"),
    ("I110", "transformer and controls", "rials"),
    ("I112", "installation", "rials"),
    ("I177", "machinery total", "rials"),
    ("I178", "utilities (gas piping, cabling)", "rials"),
    ("I181", "contingency on fixed capital", "rials"),
    ("I185", "fixed capital", "rials"),
    ("I188", "working capital: materials", "rials"),
    ("I189", "working capital: salaries", "rials"),
    ("I190", "working capital: utilities", "rials"),
    ("I191", "working capital", "rials"),
    ("C198", "total investment", "rials"),
    ("I209", "depreciation", "rials/yr"),
    ("I212", "cost 1: materials (fuel)", "rials/yr"),
    ("I213", "cost 2: salaries", "rials/yr"),
    ("I214", "cost 3: electricity and land rent", "rials/yr"),
    ("I215", "cost 4: maintenance", "rials/yr"),
    ("I216", "cost 5: contingency (5% of 1-4)", "rials/yr"),
    ("I217", "cost 6: admin and sales (1% of 1-5)", "rials/yr"),
    ("I218", "cost 7: financing", "rials/yr"),
    ("I219", "cost 8: insurance (0.2% of investment)", "rials/yr"),
    ("I220", "cost 9: depreciation", "rials/yr"),
    ("I223", "annual production cost", "rials/yr"),
    ("H225", "unit cost", "rials/kWh"),
    ("D10", "profit", "rials/yr"),
    ("D11", "return on investment", "share"),
    ("D12", "payback", "years"),
]


def read(path):
    """Cell values by A1 reference. All mapped cells are in columns A to J, so one letter each."""
    s = xlrd.open_workbook(path).sheet_by_index(SHEET)
    return {cell: s.cell_value(int(cell[1:]) - 1, ord(cell[0]) - ord("A")) for cell, _, _ in CELLS}


def main(gas_path, biogas_path):
    gas, bio = read(gas_path), read(biogas_path)
    target = Path(__file__).resolve().parents[1] / "data" / "workbook_cells.csv"
    target.parent.mkdir(exist_ok=True)
    with open(target, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cell", "item", "unit", "gas", "biogas"])
        for cell, item, unit in CELLS:
            w.writerow([cell, item, unit, gas[cell], bio[cell]])
    print(f"wrote {target}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
