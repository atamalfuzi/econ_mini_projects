"""Every input to the model, with its source.

Report: an unpublished 2018 feasibility study for a site in Tabriz, Iran (in Persian), cited by PDF page.
Workbooks: the study's two business-plan workbooks, one per fuel (CNG.xls for natural gas, Bio.xls for biogas),
first sheet '90% تبریز' ("90% Tabriz"), cited by cell. The cells used are copied into data/workbook_cells.csv by
tools/extract_workbooks.py. The workbooks' second sheet is an earlier 1 MW plan by another author and is not used.
Values marked "my choice" are in neither source.
All money is in 2018 rials at constant prices: neither workbook escalates any price.
"""
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUT, FIGURES, DATA = ROOT / "output", ROOT / "figures", ROOT / "data"
FUELS = ("gas", "biogas")

# --- Air-standard cycle (report section 2-6, p. 39, and the equation listing in section 2-8, p. 41) ---
# Heat is added at constant volume (T3/T2 = P3/P2 and q_in = c_v (T3 - T2)), so this is an Otto cycle,
# though the report calls the engine a diesel engine.
P1 = 100.0         # kPa, state 1 (p. 39, p. 41)
T1 = 300.0         # K, state 1 (p. 39, p. 41)
T3 = 2000.0        # K, peak temperature (p. 39; set outside the equations in the p. 41 listing)
CV = 0.717         # kJ/(kg K) (p. 39, p. 41)
CP_TEXT = 1.004    # kJ/(kg K), as printed in the text (p. 39)
CP_CODE = 1.04     # kJ/(kg K), as printed in the equation listing (p. 41); the value behind CR = 8.211
REPORTED_CR = 8.211     # compression ratio at maximum net work (abstract, p. 68; figure 3-1, p. 43)
REPORTED_WNET = 538.3   # kJ per kg of air, maximum net work (abstract, p. 68; figure 3-1, p. 43)
LHV = {"gas": 50000.0, "biogas": 21000.0}   # kJ/kg, LHV_CH4 and LHV_biogas (p. 41); gas is taken as methane
DENSITY = {"gas": 0.7, "biogas": 1.2}       # kg/m3, used to turn fuel mass into volume (pp. 54-55)
REPORTED_FUEL_KG_S = {"gas": 0.01757, "biogas": 0.04184}  # kg/s at maximum output (pp. 54-55)
METHANE_HHV = 55500.0   # kJ/kg, higher heating value of methane (standard property), to convert HHV to LHV

# --- Plant (workbooks, same in both unless noted) ---
POWER_KW = 538.3    # kW: the report reads the 538.3 kJ/kg optimum as the plant's output (p. 51), i.e. 1 kg/s of air
HOURS = 7680        # h/yr: E36 = 4,134,144 kWh = 538.3 kW x 7,680 h (also p. 62)
TARIFF = {"gas": 1000.0, "biogas": 3500.0}   # rials/kWh, guaranteed purchase prices (p. 51, p. 62; Bio G36)
TARIFF_GAS_WORKBOOK = 2700.0  # rials/kWh, the hypothetical gas price the report sets instead (p. 62; CNG G36)
FUEL_PRICE = {"gas": 607.0,        # rials/m3, gas sold to private power plants (CNG G145; p. 54)
              "biogas": 200000.0}  # rials/m3, upgrading (concentration and cleaning) of biogas (Bio G145; p. 54).
#                                    The raw biogas itself costs nothing (Bio G146; p. 54).
WORKBOOK_FUEL_M3_H = {"gas": 90.36, "biogas": 125.52}  # m3/h (E145; pp. 54-55)

# --- Capital cost, rials (workbook rows 91-113, 134-138, 171-191; report tables 3-1 to 3-17) ---
LAND = 2_000_000_000          # I174: 200 m2 x 10,000,000 rials (A93:E93), both fuels
BUILDING = 1_004_000_000      # I176: steel shed 800,000,000 (I101) + foundation 204,000,000 (I102)
ENGINE_USD_PER_KW = 1000.0    # engine price (p. 52); x 538.3 kW x 42,000 rials/$ = 22,608,600,000 (I106)
COMPRESSOR = {"gas": 0.0, "biogas": 8_200_000_000.0}  # I108: biogas compressor, with 30% customs duty (p. 53)
TRANSFORMER_SHARE = 0.15      # transformer and controls, share of engine price (p. 52; I110)
INSTALL_SHARE = 0.05          # installation, share of engine price (p. 52; I112)
UTILITIES = 500_000_000       # I178: gas piping 300,000,000 (G136) + cabling 200,000,000 (G137)
CONTINGENCY = 0.05            # I181: 5% of the fixed items above
WORKING_MONTHS = 2            # I188:I190: two months of materials, salaries and utilities

# --- Annual costs, rials (workbook rows 148-168 and 210-223; report tables 3-7 to 3-22) ---
SALARIES = 472_800_000        # I213: two staff at 15,000,000 a month for 15.76 months (I165:I166, A168)
UTILITY_BILLS = 4_000_000_000  # I214: electricity 2,000,000,000 (I150) and land rent 2,000,000,000 (I151);
#                                the report calls the two items water and electricity (table 3-10, p. 55)
MAINTENANCE = {"building": 0.02, "machinery": 0.07, "utilities": 0.05}   # share of asset value a year (G157:G159)
OPEX_CONTINGENCY = 0.05       # I216: 5% of cost items 1-4
ADMIN = 0.01                  # I217: 1% of cost items 1-5
INSURANCE = 0.002             # I219: 0.2% of total investment
DEPRECIATION = {"building": 0.10, "machinery": 0.13, "utilities": 0.12, "contingency": 0.05}  # H203:H208

# --- Discounting: neither workbook has a discount rate or a project life ---
RATE = 0.05   # my choice: the one interest rate in the workbooks, the 5% charged on any loan-financed capital (B218)
LIFE = 8      # years, my choice: machinery is depreciated at 13% a year (H204), so written off in 7.7 years

# --- Workbook results, used only to check the cost build-up (first-sheet cells) ---
WORKBOOK = {
    "gas": {"fixed": 32_166_036_000, "working": 745_475_808.0866666, "depreciation": 3_763_927_400,
            "annual_cost": 10_635_039_635.671635, "unit_cost": 2572.488920480669,
            "profit": 527_149_164.3283634, "payback": 7.669756369224317},           # CNG I185 I191 I209 I223 H225 D10 D12
    "biogas": {"fixed": 40_776_036_000, "working": 749_650_666.6666666, "depreciation": 4_850_427_400,
               "annual_cost": 12_374_059_610.533333, "unit_cost": 2993.137058247931,
               "profit": 2_095_444_389.4666653, "payback": 5.978470079398801},     # Bio I185 I191 I209 I223 H225 D10 D12
}
REPORT_PAYBACK_BIOGAS = 4.82   # years, as printed in the report (p. 64); its formula puts depreciation in place of profit

# --- Exchange rates, 2018 ---
# Both from RFE/RL, "Iran Tries To Unify Exchange Rates To Halt Currency Decline", 10 April 2018.
RIALS_PER_USD = 42_000         # official rate from 10 April 2018; also the rate the report uses (p. 52)
RIALS_PER_USD_MARKET = 60_000  # unregulated-market rate on 9 April 2018

# --- Comparison values, not used in the base case ---
ETA_ENGINE_HHV = 0.345   # electrical efficiency of a 633 kW gas engine CHP unit, HHV basis
#                          (US EPA CHP Partnership, Catalog of CHP Technologies, 2015, table 2-2, system 2)
EPA_COST_USD_PER_KW = 2837   # total installed cost of the same unit, 2013 US$ per kW (same table)

# --- Published biogas upgrading costs, in euro cents per kWh of gross calorific value ---
# DBFZ, "Retrofitting of existing biogas plants towards upgrading to biomethane", IEA Bioenergy Task 37 meeting,
# 15 April 2021, slide 11 (data: DBFZ 2018, in Beil et al. 2019).
UPGRADE_CT_STANDARD = (1.0, 2.0)  # slide text: "for standard upgrading capacities (~700 m3/h) in general between 1 - 2 ct"
UPGRADE_CT_SMALL = (2.3, 4.6)     # read from the slide's chart: the plants plotted at about 100-150 m3/h of raw biogas
USD_PER_EUR = 1.181               # 2018 average of the European Central Bank's euro reference rate

# --- Sensitivity ranges (low, high), my choice: +/-50% for prices and capital cost ---
RANGES = {
    "price_gas": (0.5 * FUEL_PRICE["gas"], 1.5 * FUEL_PRICE["gas"]),
    "price_biogas": (0.5 * FUEL_PRICE["biogas"], 1.5 * FUEL_PRICE["biogas"]),
    "tariff_gas": (0.5 * TARIFF["gas"], 1.5 * TARIFF["gas"]),
    "tariff_biogas": (0.5 * TARIFF["biogas"], 1.5 * TARIFF["biogas"]),
    "eta": (ETA_ENGINE_HHV * METHANE_HHV / LHV["gas"], None),  # low: the EPA engine on an LHV basis; high: the cycle
    "capex": (0.5, 1.5),       # multiplies every fixed capital item except land, for both fuels
    "rate": (0.0, 0.15),
    "life": (5, 20),
}
MC_DRAWS, MC_SEED = 20_000, 2018
