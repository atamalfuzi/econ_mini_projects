# econ_mini_projects

[![tests](https://github.com/atamalfuzi/econ_mini_projects/actions/workflows/tests.yml/badge.svg)](https://github.com/atamalfuzi/econ_mini_projects/actions/workflows/tests.yml)

Four small, self-contained pieces of economic research. Each asks one question, answers it from open data or a documented source, and checks itself against published numbers or closed forms. Every folder has its own README, data script, tests and figures, and runs on its own.

> **Personal project.** This is my own analysis of publicly available data. It is not associated with my work for any current or past employer and does not represent their views.

| Folder | Question | Short answer | Methods |
|---|---|---|---|
| [charter_schools_arizona](charter_schools_arizona/) | Did Arizona's charter schools draw white students out of traditional public schools? | The published two-year estimate (−2.6 points) reproduces at −2.7. But Arizona's white share was already falling faster than New Mexico's before charters opened. Once that trend or county demographics are allowed for, there is no clear sign of skimming. Pupil-teacher ratios rose by about 1.7 relative to New Mexico. | Difference-in-differences, event study with school and year fixed effects, district-clustered errors, trend sensitivity |
| [equity_premium](equity_premium/) | How large has the US equity premium been, and what would a model need to explain it? | 5.2 points a year since 1871. Mehra and Prescott's economy needs risk aversion of about 21 to match it, and its risk-free rate is then 21%. A rare-disaster state with a 1.7% annual chance and a 36% to 49% fall in consumption matches both at risk aversion of 3 to 5. | Markov-chain asset pricing, Hansen-Jagannathan bound, rare-disaster calibration |
| [long_horizon_portfolio](long_horizon_portfolio/) | Should a long-term investor hold more stocks when the dividend yield is high? | In the Kim and Omberg model, yes, and hedging demand adds 21% to 48% of the myopic share at 30 years. But the predictability behind it is weak: t = 1.2, smaller after Stambaugh's correction, and no better than the historical mean out of sample. | Predictive regression, bias correction, closed-form portfolio choice checked by numerical ODE, out-of-sample R² |
| [rbc_canada](rbc_canada/) | How much of Canada's business cycle does a basic real business cycle model reproduce? | About 80% of output's volatility (1.12% against 1.37%), and the right ordering of consumption and investment. It misses hours, which move half as much as in the data, and labour productivity. | Calibrated RBC model, log-linearisation, Blanchard-Kahn, Solow residual, HP-filtered moments |
## Run one

```bash
cd charter_schools_arizona
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # .venv/bin/pip on macOS and Linux
.venv/Scripts/python -m pytest
```

Each folder commits the small processed data its tests and figures need, so the tests never download. Its `data.py` rebuilds that data from the original sources. Raw downloads go in `data/raw/`, which git ignores.

## License

The code is under the [MIT licence](LICENSE). The data belong to their publishers: NCES and the US Census Bureau, Robert Shiller, and Statistics Canada. Each folder's README names its sources.
