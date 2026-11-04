# Proposed site text

For the session that integrates the website. Nothing here has been added to the site.

## Portfolio entry

**Title:** Five mini research projects

**Type and year:** Open data analysis in Python, 2026

**Text:**
- Arizona's charter schools: the published skimming estimate reproduces, but the event study shows the decline began before charters opened.
- The US equity premium since 1871, and what a consumption model needs to explain it.
- Long-horizon portfolio choice when the dividend yield predicts returns.
- How much of Canada's business cycle a basic real business cycle model reproduces.
- The break-even electricity price for a small engine run on natural gas or on biogas.

Each project answers one question, checks itself against published numbers or closed forms, and runs on its own.

**Links:** code at https://github.com/atamalfuzi/econ_mini_projects

## The five projects

### Did Arizona's charter schools draw white students out of public schools?

A replication of Dee and Fu (2004) on Arizona and New Mexico schools, extended from two years to sixteen. The published two-year estimate reproduces, but Arizona's white share was already falling faster before charters opened. Once that trend or county demographics are allowed for, there is no clear sign of skimming. Pupil-teacher ratios did rise relative to New Mexico.

- Two-year estimate: −2.7 points, against Dee and Fu's −2.6.
- Arizona's relative decline before 1995: about 1.2 points a year.
- Against Arizona's own earlier trend, with the county control: +1.6 points (SE 1.5).
- Pupil-teacher ratio: +1.7 over 1999-2005 (SE 0.4).

Link: https://github.com/atamalfuzi/econ_mini_projects/tree/main/charter_schools_arizona

### How large has the US equity premium been, and what would a model need to explain it?

The equity premium in Robert Shiller's annual US data since 1871, and what a consumption-based model with power utility needs to produce it. Mehra and Prescott's two-state economy, recalibrated to 1889-2007 consumption, matches the premium only at a risk aversion of about 21, with a 21% risk-free rate. Adding a rare disaster state as in Rietz and Barro matches both the premium and the risk-free rate at risk aversion of 3 to 5, if a disaster has a 1.7% chance each year and cuts consumption by roughly 36% to 49%.

- Premium, 1871-2011: 5.2 points a year.
- Risk aversion to match the 1889-2007 premium in Mehra and Prescott's economy: 21.
- Hansen-Jagannathan bound, 1889-2007: risk aversion of at least 8.3.

Link: https://github.com/atamalfuzi/econ_mini_projects/tree/main/equity_premium

### Should a long-term investor hold more stocks when the dividend yield is high?

The Kim and Omberg (1996) portfolio model, with a mean-reverting risk premium, fitted to Shiller's annual US data from 1872 to 2011. In the model a long-horizon investor holds more stocks when the dividend yield is high. Hedging demand adds to that and grows with the horizon, but stays smaller than the myopic demand. The predictability behind it is weak: the slope is not significant, shrinks after Stambaugh's bias correction, and does not beat the historical mean out of sample.

- Stock share at 30 years, risk aversion 5: 48% at the average dividend yield, 29% at the January 2016 yield.
- Predictive slope: 0.043 (t = 1.2); bias-corrected 0.025.
- Out-of-sample R², 1892-2011: −1.3%.

Link: https://github.com/atamalfuzi/econ_mini_projects/tree/main/long_horizon_portfolio

### How much of Canada's business cycle does a basic real business cycle model reproduce?

The standard real business cycle model is calibrated to Canadian national accounts, driven by technology shocks estimated from Canada's Solow residual, and compared with Canadian cycles from 1976 to 2019. It produces most of output's volatility and the right ordering of consumption and investment. It misses hours, which move too little, and labour productivity, which moves with output in the model but only loosely in the data.

- Output volatility: 1.12% in the model, 1.37% in the data.
- Hours relative to output: 0.49 in the model, 1.00 in the data.
- Correlation of hours with output per hour: 0.91 in the model, −0.28 in the data.

Link: https://github.com/atamalfuzi/econ_mini_projects/tree/main/rbc_canada

### At what guaranteed price does a small gas engine break even on natural gas or on biogas?

A rebuild of an unpublished 2018 feasibility study for a 538 kW engine in Tabriz, Iran, run on natural gas or on upgraded biogas. The engine model reproduces, and gas needs about 2,930 rials per kWh against a guaranteed 1,000, as the study found. The study's finding that biogas pays came from its business plans counting one hour of upgrading cost as a year's. At published upgrading costs biogas does not break even at its 3,500 tariff either. It loses less than gas only at the costs of large upgrading plants.

- Gas break-even tariff: 2,933 rials per kWh, or 7.0 US cents at the 2018 official rate.
- Biogas break-even: 3,304 rials per kWh as the plans are printed. With a full year of fuel, 4,260 to 7,720 at published upgrading costs, and 53,155 at the study's own price.

Link: https://github.com/atamalfuzi/econ_mini_projects/tree/main/biogas_engine_tariff
