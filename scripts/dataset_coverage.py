"""What PolicyEngine's certified US microdata says about veterans.

Reads the certified Microcosm US dataset (populace_us_2024.h5) and writes
weighted aggregates, never records, to outputs/dataset_coverage.json.

    .venv/bin/python -I scripts/dataset_coverage.py PATH/TO/populace_us_2024.h5

The file comes from the Hugging Face dataset policyengine/populace-us
(release populace-us-2024-spm-20260915, the one the policyengine.py bundle
loads by default).
"""

import hashlib
import json
import pathlib
import sys

import pandas as pd

OUT = pathlib.Path(__file__).resolve().parents[1] / "outputs"

PERSON_COLUMNS = [
    "person_household_id",
    "age",
    "veterans_benefits",
    "is_military",
    "has_va_health_coverage_at_interview",
    "has_tricare_health_coverage_at_interview",
    "has_champva_health_coverage_at_interview",
]
# Inputs a military retirement or veteran-status analysis would need.
WANTED = [
    "military_retirement_pay",
    "military_retirement_pay_survivors",
    "is_veteran",
    "is_permanently_disabled_veteran",
    "is_fully_disabled_service_connected_veteran",
    "years_in_military",
]
AGE_BANDS = [(0, 17), (18, 34), (35, 54), (55, 64), (65, 74), (75, None)]


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(path: pathlib.Path):
    with pd.HDFStore(path, "r") as store:
        person_columns = list(store.get_storer("/person").attrs.non_index_axes[0][1])
        person = store.select("/person", columns=PERSON_COLUMNS)
        household = store.select(
            "/household", columns=["household_id", "household_weight"]
        )
    weight = person.person_household_id.map(
        household.set_index("household_id").household_weight
    )
    assert weight.notna().all()
    va = person.veterans_benefits
    receives = va > 0

    def people(mask):
        return {
            "weighted_millions": round(float(weight[mask].sum()) / 1e6, 2),
            "records": int(mask.sum()),
        }

    def age_band(lo, hi):
        mask = receives & (person.age >= lo)
        if hi is not None:
            mask &= person.age <= hi
        return people(mask)

    va_cover = person.has_va_health_coverage_at_interview.astype(bool)
    result = {
        "dataset": path.name,
        "sha256": sha256(path),
        "year": 2024,
        "population_weighted_millions": round(float(weight.sum()) / 1e6, 2),
        "receives_va_payments": people(receives),
        "va_payments_total_billions": round(float((weight * va).sum()) / 1e9, 1),
        "va_payment_mean_per_recipient": round(
            float((weight * va)[receives].sum() / weight[receives].sum())
        ),
        "receives_va_payments_by_age": {
            (f"{lo}-{hi}" if hi is not None else f"{lo}+"): age_band(lo, hi)
            for lo, hi in AGE_BANDS
        },
        "is_military": people(person.is_military.astype(bool)),
        "va_health_coverage": people(va_cover),
        "va_health_coverage_and_va_payments": people(va_cover & receives),
        "va_health_coverage_without_va_payments": people(va_cover & ~receives),
        "tricare_coverage": people(
            person.has_tricare_health_coverage_at_interview.astype(bool)
        ),
        "champva_coverage": people(
            person.has_champva_health_coverage_at_interview.astype(bool)
        ),
        "columns_present": {
            c: c in person_columns for c in PERSON_COLUMNS[2:] + WANTED
        },
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "dataset_coverage.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]))
