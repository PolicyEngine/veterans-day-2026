# Veterans Day 2026: military retired pay and veteran rules in PolicyEngine-US

> **Work in progress.** We are checking every state's result against its law and
> tax forms. Until that check finishes, treat the numbers here as preliminary and
> don't cite them.

This repository asks three questions of [PolicyEngine-US](https://github.com/PolicyEngine/policyengine-us):

1. **How much state income tax does each state levy on military retired pay in 2026?**
   `scripts/state_military_retirement.py` runs PolicyEngine household calculations
   in all 50 states and DC for two married couples.
2. **Which PolicyEngine-US rules turn on military service or veteran status?**
   `scripts/inventory.py` lists every parameter and variable that names a veteran or
   military input (`outputs/inventory_raw.csv`).
3. **What does PolicyEngine's microdata record about veterans?**
   `scripts/dataset_coverage.py` reads the certified US dataset and reports which
   veteran and military columns it carries (`outputs/dataset_coverage.json`).

## Households and scenarios

Both couples file jointly in tax year 2026 and have no dependents. The retiree is
the older spouse and the head of the tax unit, served 20 years
(`years_in_military`) and has no service-connected disability; the spouse has no
income.

| Archetype | Ages | Service | Military retired pay | Other income |
|---|---|---|---|---|
| `working_45` | 45 and 43 | 2001 to 2020 | $30,000 | $60,000 of the retiree's wages |
| `retired_67` | 67 and 65 | 1977 to 1996 | $45,000 | $30,000 of the retiree's Social Security |

Kentucky and Oregon exempt the part of a federal pension earned before a cutoff,
and PolicyEngine-US takes the service history as inputs. In the military
scenario the script sets them from the service years: Kentucky's months of
service before 1998 (all 240 for the 67-year-old, none for the 45-year-old) and
Oregon's subtraction for service before October 1, 1991 (177 of 240 months, or
$33,188 of the 67-year-old's pay).

$30,000 a year comes to $2,500 a month, close to the $2,469 average monthly
nondisability retired pay of enlisted retirees in September 2022 (DoD Office of the
Actuary, [Statistical Report on the Military Retirement System, FY2022](https://actuary.defense.gov/Portals/15/Documents/Stat%20report/MRS%20StatRpt%202022%20v999.pdf), p. 55).

Each couple runs in three scenarios:

- `military`: the pension enters as `military_retirement_pay`;
- `civilian`: the same amount enters as `taxable_private_pension_income`;
- `none`: no pension.

From these, `outputs/state_military_retirement_2026.csv` reports, for each state:

- `tax_on_military_pay` = state income tax (`military`) minus state income tax (`none`);
- `military_break` = state income tax (`civilian`) minus state income tax (`military`), the
  value of the rules a state gives military retirees and not other retirees.

For each scenario the CSV also records state income tax and state AGI, federal income
tax, federal AGI and taxable Social Security, the inputs to the credits and deductions
that the post explains.

State income tax here means PolicyEngine's `state_income_tax` for the tax unit,
after credits. Refundable credits reduce it, so a state can show a negative
`tax_on_military_pay`: Alabama and Missouri let filers deduct federal income tax, and
the pension raises it. A pension that cuts an income-tested credit raises
`tax_on_military_pay` by the credit lost.

`outputs/state_military_retirement_grid_2026.csv` widens the grid to ages 45 and
67, pensions from $20,000 to $80,000, and wages of $0 or $60,000.
`outputs/post_charts/` holds the blog post's map and bar chart specs, which
`scripts/post_charts.py` writes from the CSV.

## Model version

`outputs/run_metadata.json` records the PolicyEngine-US and policyengine-core
versions behind every output. A run on a PolicyEngine-US checkout (for example a
pull request branch, with `PYTHONPATH` pointing at it) records the commit and
branch in place of a release number.

The households run on PolicyEngine-US directly. The policyengine.py bundle that
powers the PolicyEngine web app pins its own PolicyEngine-US release, so the web
calculator can trail these results until the bundle picks up the same release.

## Veteran and military rules

`outputs/inventory_meta.json` counts the files. In PolicyEngine-US 2.105.0, 482
parameter and variable files mention veterans or military service, and 300 of
them name one of 22 veteran or military inputs. Most read
`military_retirement_income` (117 files) or `veterans_benefits` (149), the VA
payments that count as income for SNAP, SSI, TANF, LIHEAP and other programs.

## Data coverage

These are household calculations and use no survey data. PolicyEngine's
certified US dataset (`populace_us_2024.h5`, sha256
`6496cc4393d4d3c6574f76eca231de5898c803b9067645591fd5c4d3e65aee84`) carries
the CPS ASEC's VA payments, `is_military` and the VA, TRICARE and CHAMPVA coverage
flags. It carries no veteran-status or military retired pay column.
PolicyEngine-US sets `is_veteran` to true when `veterans_benefits` exceeds zero, so in
microsimulation its veteran rules reach only people with VA payments.

| Measure | PolicyEngine dataset, 2024 | Benchmark |
|---|---|---|
| People with VA payments | 5.12 million (2,389 records) | 5.99 million disability compensation recipients at the end of FY2024 ([VBA Annual Benefits Report, FY2025](https://www.benefits.va.gov/REPORTS/abr/docs/2025-compensation.pdf), p. 77) |
| VA payments | $121.7 billion | $177.9 billion of compensation and pension account obligations in FY2024 ([VA FY2026 budget, vol. 3](https://department.va.gov/wp-content/uploads/2025/06/2026-Volume-3-Burial-and-Benefits-Programs-and-Departmental-Administration.pdf), p. 145) |
| Veterans | none recorded | 15.7 million civilian veterans age 18 and over in 2024 ([ACS table S2101](https://data.census.gov/table/ACSST1Y2024.S2101)) |
| Military retirees | none recorded | 2.0 million retirees paid by DoD on September 30, 2022 ([DoD statistical report](https://actuary.defense.gov/Portals/15/Documents/Stat%20report/MRS%20StatRpt%202022%20v999.pdf), pp. 22 and 61) |

VA payments in the CPS also include survivor and education benefits, so they
match no single VA program. The dataset's figures cover calendar 2024 incomes;
VA reports by fiscal year.

## Limitations

- Each couple files jointly as full-year residents of one state. Retirees with
  other service dates, a service-connected disability, or a residency history
  outside Montana's five-year window can owe a different amount.
- The calculations leave out local income taxes and VA disability compensation.
- `tax_on_military_pay` includes changes in income-tested state credits, so it
  can exceed the tax a state levies on the pay itself.

## Reproduce

```bash
uv venv --python 3.12 .venv
VIRTUAL_ENV=.venv uv pip install -r requirements.txt
.venv/bin/python scripts/state_military_retirement.py --grid
.venv/bin/python scripts/inventory.py
.venv/bin/python scripts/dataset_coverage.py <path to populace_us_2024.h5>
.venv/bin/python scripts/post_charts.py
```

`scripts/trace_state.py ST archetype [variables...]` prints one state's
intermediate tax variables for each scenario, for example
`.venv/bin/python scripts/trace_state.py MT working_45 mt_subtractions`.
