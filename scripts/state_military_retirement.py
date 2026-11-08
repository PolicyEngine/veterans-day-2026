"""State income tax on military retired pay, 2026, in every state and DC.

For each household archetype and each of the 51 jurisdictions, run three
PolicyEngine-US household simulations that differ only in the retiree's
pension:

  military  - the pension is military retired pay (military_retirement_pay)
  civilian  - the same amount is a taxable private pension
  none      - no pension

and report

  tax_on_military_pay  = state tax(military) - state tax(none)
  military_break       = state tax(civilian) - state tax(military)

so `military_break` is what a state's military-specific rules save a retiree
relative to a neighbor with the same private pension. All 51 jurisdictions run
as separate households inside one simulation per archetype and scenario.
"""

import argparse
import json
import pathlib
import sys

import pandas as pd
from policyengine_us import Simulation

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from model_source import model_source  # noqa: E402

YEAR = 2026
OUT = pathlib.Path(__file__).resolve().parents[1] / "outputs"

STATES = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]

# Married couples filing jointly, no dependents. The retiree is the older
# spouse, so PolicyEngine makes them the tax-unit head. years_in_military is
# 20 because North Carolina's deduction requires 20 years of service.
ARCHETYPES = {
    "working_45": dict(
        label="Age 45, retired after 20 years, working a second career",
        head_age=45,
        spouse_age=43,
        pension=30_000,
        head_wages=60_000,
        spouse_wages=0,
        social_security=0,
    ),
    "retired_67": dict(
        label="Age 67, fully retired, with Social Security",
        head_age=67,
        spouse_age=65,
        pension=45_000,
        head_wages=0,
        spouse_wages=0,
        social_security=30_000,
    ),
}

# A wider grid for the CSV appendix.
GRID = [
    dict(
        head_age=a,
        spouse_age=a - 2,
        pension=p,
        head_wages=w,
        spouse_wages=0,
        social_security=(24_000 if a >= 67 else 0),
    )
    for a in (45, 67)
    for p in (20_000, 30_000, 50_000, 80_000)
    for w in (0, 60_000)
]


def situation(arch, scenario):
    people, units = (
        {},
        {
            k: {}
            for k in (
                "tax_units",
                "families",
                "spm_units",
                "marital_units",
                "households",
            )
        },
    )
    for i, state in enumerate(STATES):
        head, spouse = f"{state}_head", f"{state}_spouse"
        h = {
            "age": {YEAR: arch["head_age"]},
            "employment_income": {YEAR: arch["head_wages"]},
            "years_in_military": {YEAR: 20},
            "military_retirement_pay": {
                YEAR: arch["pension"] if scenario == "military" else 0
            },
            "taxable_private_pension_income": {
                YEAR: arch["pension"] if scenario == "civilian" else 0
            },
        }
        if arch["social_security"]:
            h["social_security_retirement"] = {YEAR: arch["social_security"]}
        people[head] = h
        people[spouse] = {
            "age": {YEAR: arch["spouse_age"]},
            "employment_income": {YEAR: arch["spouse_wages"]},
        }
        members = [head, spouse]
        units["tax_units"][f"{state}_tu"] = {"members": members}
        units["families"][f"{state}_f"] = {"members": members}
        units["spm_units"][f"{state}_spm"] = {"members": members}
        units["marital_units"][f"{state}_mu"] = {"members": members}
        units["households"][f"{state}_hh"] = {
            "members": members,
            "state_code": {YEAR: state},
        }
    return {"people": people, **units}


def run(arch):
    out = {}
    for scenario in ("military", "civilian", "none"):
        sim = Simulation(situation=situation(arch, scenario))
        out[scenario] = {
            "state_income_tax": sim.calculate("state_income_tax", YEAR),
            "state_agi": sim.calculate("state_agi", YEAR),
            "federal_income_tax": sim.calculate("income_tax", YEAR),
        }
    df = pd.DataFrame({"state": STATES})
    for scenario, vals in out.items():
        for k, v in vals.items():
            df[f"{k}_{scenario}"] = v.round(2)
    df["tax_on_military_pay"] = (
        df.state_income_tax_military - df.state_income_tax_none
    ).round(2)
    df["military_break"] = (
        df.state_income_tax_civilian - df.state_income_tax_military
    ).round(2)
    df["effective_rate_on_military_pay"] = (
        df.tax_on_military_pay / arch["pension"]
    ).round(4)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--grid", action="store_true", help="also run the appendix grid"
    )
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    meta = {"year": YEAR, **model_source(), "archetypes": ARCHETYPES}
    frames = []
    for key, arch in ARCHETYPES.items():
        df = run(arch)
        df.insert(0, "archetype", key)
        frames.append(df)
        print(f"\n{arch['label']}: ${arch['pension']:,} military retired pay")
        print(
            df[
                [
                    "state",
                    "tax_on_military_pay",
                    "military_break",
                    "effective_rate_on_military_pay",
                ]
            ]
            .sort_values("tax_on_military_pay", ascending=False)
            .to_string(index=False)
        )
    pd.concat(frames).to_csv(OUT / "state_military_retirement_2026.csv", index=False)
    if args.grid:
        rows = []
        for arch in GRID:
            df = run(arch)
            for k, v in arch.items():
                df[k] = v
            rows.append(df)
        pd.concat(rows).to_csv(
            OUT / "state_military_retirement_grid_2026.csv", index=False
        )
    (OUT / "run_metadata.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
