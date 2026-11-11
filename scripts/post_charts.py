"""Write the blog post's chart blocks from the calculation outputs.

Reads outputs/state_military_retirement_2026.csv and outputs/run_metadata.json
and writes outputs/post_charts/*.json, one PolicyEngine blog ```chart spec
per file (types "stateMap" and "bar", as the website's BlogChart.tsx parses
them; the bars run horizontally, which needs the "orientation" and "legend"
fields that PolicyEngine/policyengine-app-v2#1523 adds). Rerun after every calculation so the post's numbers match the CSV.
"""

import json
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "post_charts"

NO_INCOME_TAX = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

TAX_BINS = [
    {"below": 1, "label": "$0 or less"},
    {"below": 500, "label": "$1 to $499"},
    {"below": 1000, "label": "$500 to $999"},
    {"below": 2000, "label": "$1,000 to $1,999"},
    {"label": "$2,000 and up"},
]


def source_line(meta: dict) -> str:
    """Name the release when the run used one; a checkout's hash stays in run_metadata.json."""
    version = (
        f" {meta['policyengine_us']}" if meta["policyengine_us_from"] == "release" else ""
    )
    return (
        f"Source: PolicyEngine-US{version} household calculations for {meta['year']}; "
        "github.com/PolicyEngine/veterans-day-2026."
    )


def state_map(df: pd.DataFrame, arch: dict, meta: dict, title: str) -> dict:
    # States with no broad income tax carry no value, so the map prints a dash.
    rows = [
        {"state": r.state, "tax": round(float(r.tax_on_military_pay))}
        for r in df.itertuples()
        if r.state not in NO_INCOME_TAX
    ]
    return {
        "type": "stateMap",
        "title": title,
        "subtitle": arch["subtitle"],
        "stateKey": "state",
        "valueKey": "tax",
        "data": rows,
        "bins": TAX_BINS,
        **({"note": arch["note"]} if arch["note"] else {}),
        "format": {"decimals": 0, "prefix": "$", "separator": True},
        "source": source_line(meta),
    }


def taxing_states_bar(df: pd.DataFrame, arch: dict, meta: dict, title: str) -> dict:
    taxed = df[df.tax_on_military_pay >= 1].sort_values(
        "tax_on_military_pay", ascending=False
    )
    # Horizontal bars put the dollars on the x-axis; the subtitle names the
    # one series, so the chart needs no legend.
    return {
        "type": "bar",
        "title": title,
        "subtitle": arch["subtitle"],
        "orientation": "horizontal",
        "legend": False,
        "xKey": "state",
        "series": [
            {"key": "tax", "name": "Extra state income tax", "color": "primary"}
        ],
        "data": [
            {"state": STATE_NAMES[r.state], "tax": round(float(r.tax_on_military_pay))}
            for r in taxed.itertuples()
        ],
        "format": {"decimals": 0, "prefix": "$", "separator": True},
        "source": source_line(meta),
    }


def negative_note(df: pd.DataFrame) -> str:
    names = {
        "AL": "Alabama",
        "IA": "Iowa",
        "LA": "Louisiana",
        "MO": "Missouri",
        "MT": "Montana",
        "OR": "Oregon",
    }
    below = sorted(df[df.tax_on_military_pay <= -1].state)
    if not below:
        return ""
    unknown = set(below) - set(names)
    assert not unknown, f"name these states and check why their tax falls: {unknown}"
    listed = " and ".join(names[s] for s in below)
    return (
        f"{listed} let filers deduct federal income tax, which rises with the "
        "pay, so the couple owes less state income tax there with the pay than "
        "without it. A dash marks a state with no broad income tax."
    )


def main():
    df = pd.read_csv(ROOT / "outputs" / "state_military_retirement_2026.csv")
    meta = json.loads((ROOT / "outputs" / "run_metadata.json").read_text())
    archetypes = meta["archetypes"]
    # The notes say these states levy no tax on wages or pensions; check it.
    none = df[df.state.isin(NO_INCOME_TAX)]
    tax_columns = [c for c in df.columns if c.startswith("state_income_tax_")]
    assert (none[tax_columns] == 0).all().all(), "a no-income-tax state shows tax"
    text = {
        "working_45": {
            "subtitle": (
                "Extra state income tax a married couple owes when one spouse, "
                "age 45, receives $30,000 of military retired pay on top of "
                "$60,000 of wages, 2026"
            ),
            "note": negative_note(df[df.archetype == "working_45"]),
        },
        "retired_67": {
            "subtitle": (
                "Extra state income tax a married couple, ages 67 and 65, owes "
                "because of $45,000 of military retired pay, with $30,000 of Social "
                "Security, 2026"
            ),
            "note": negative_note(df[df.archetype == "retired_67"]),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for key in archetypes:
        sub = df[df.archetype == key]
        arch = {**archetypes[key], **text[key]}
        pay = f"${archetypes[key]['pension']:,}"
        specs = {
            f"map_{key}": state_map(
                sub, arch, meta, f"How {pay} of military retired pay changes state income tax"
            ),
            f"bar_{key}": taxing_states_bar(
                sub,
                arch,
                meta,
                f"Where {pay} of military retired pay raises state income tax",
            ),
        }
        for name, spec in specs.items():
            (OUT / f"{name}.json").write_text(json.dumps(spec, indent=2) + "\n")
    print(
        f"wrote {len(list(OUT.glob('*.json')))} chart specs to {OUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
