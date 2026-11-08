# Veterans Day 2026: veterans in PolicyEngine-US

> **Work in progress.** Results here have not yet been checked state by state against
> official sources. Don't cite them yet.

This repository asks two questions of PolicyEngine-US (`policyengine-us==2.105.0`):

1. **How does each state tax military retired pay in 2026?** For two married
   retiree households, `scripts/state_military_retirement.py` runs PolicyEngine
   household simulations in all 50 states and DC, three ways: with the pension as
   military retired pay, with the same amount as a private pension, and with no
   pension. The differences give the state income tax on the military pay and the
   value of each state's military-specific rules.
2. **What does PolicyEngine model for veterans?** `scripts/inventory.py` lists every
   parameter and variable in the installed package that refers to veteran status,
   VA benefits, military retired pay or active-duty pay
   (`outputs/inventory_raw.csv`).

## Reproduce

```bash
uv venv --python 3.12 .venv
VIRTUAL_ENV=.venv uv pip install -r requirements.txt
.venv/bin/python scripts/state_military_retirement.py --grid
.venv/bin/python scripts/inventory.py
```

`scripts/trace_state.py ST archetype [variables...]` prints one state's
intermediate tax variables for each scenario.

## Data coverage

These are household calculations; they use no survey data. PolicyEngine's
certified US microdata (`populace_us_2024`, bundle 6.16.0) carries reported VA
payments from the CPS ASEC but no veteran-status or military-retirement-pay
column, so population estimates of these provisions are not possible yet.
