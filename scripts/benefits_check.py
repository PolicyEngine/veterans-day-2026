"""Does military retired pay change either couple's benefits in PolicyEngine-US?

Runs the post's two archetypes in all 51 jurisdictions with and without the
pay (the `military` and `none` scenarios of state_military_retirement.py) and
reports every benefit in PolicyEngine-US's household_benefits aggregate, and
the health, state and local lists it nests, whose value changes with the pay.

    PYTHONPATH=PATH/TO/policyengine-us .venv/bin/python scripts/benefits_check.py

The post reports no benefit amounts. Results at 1ef50f2988: the working couple's
benefits don't change. Without the pay, the retired couple gets SNAP's minimum
allotment through categorical eligibility in 33 jurisdictions, Medicaid in
Alaska, California and New York, and a Medicare Savings Program in Hawaii. The
model applies no asset test to those health programs, and the pay ends all of
them. Minnesota's $12,660 of Minnesota Supplemental Aid comes from a model
default that treats each spouse as an individual living alone
(mn_msa_living_arrangement), so the spouse with no income of their own gets the
full individual standard. It isn't a real benefit.
"""

import json
import pathlib
import sys

import numpy as np
from policyengine_us import Simulation

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from state_military_retirement import ARCHETYPES, STATES, YEAR, situation  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[1] / "outputs"
NESTED = {
    "household_health_benefits",
    "household_state_benefits",
    "household_local_benefits",
}


def benefit_list(sim):
    p = sim.tax_benefit_system.parameters(f"{YEAR}-01-01").gov.household
    top = list(p.household_benefits)
    names = list(top)
    for n in NESTED:
        names += list(getattr(p, n))
    return top, sorted(set(names))


def main():
    result = {}
    for key, arch in ARCHETYPES.items():
        sims = {s: Simulation(situation=situation(arch, s)) for s in ("military", "none")}
        top, names = benefit_list(sims["military"])
        rows = {}
        for name in ["household_benefits", "household_net_income", *names]:
            vals = {
                s: np.asarray(sim.calculate(name, YEAR, map_to="household"))
                for s, sim in sims.items()
            }
            diff = vals["military"] - vals["none"]
            if np.abs(diff).max() >= 1 or name in ("household_benefits", "household_net_income"):
                rows[name] = {
                    st: {"none": round(float(n), 2), "military": round(float(m), 2)}
                    for st, n, m in zip(STATES, vals["none"], vals["military"])
                    if abs(m - n) >= 1 or name in ("household_benefits", "household_net_income")
                }
            # Any benefit the couple gets in either scenario, changed or not.
            got = [st for st, n, m in zip(STATES, vals["none"], vals["military"]) if n or m]
            if got and name not in rows and name not in ("household_net_income",):
                rows.setdefault("_received_unchanged", {})[name] = got
        result[key] = rows
        changed = [n for n in rows if not n.startswith("_") and n not in ("household_benefits", "household_net_income")]
        print(key, "benefits that change with the pay:", changed)
        print(key, "received but unchanged:", rows.get("_received_unchanged", {}))
        hb = rows["household_benefits"]
        d = {st: round(v["military"] - v["none"]) for st, v in hb.items()}
        print(key, "household_benefits change, min/max:", min(d.values()), max(d.values()))
        print(key, "states where household_benefits changes:", {k: v for k, v in d.items() if v})
    (OUT / "benefits_check.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
