"""Render the blog post from its template and the calculation outputs.

The template (post/template.md) writes every model number as a placeholder,
so the post's text and charts always match outputs/state_military_retirement_2026.csv
and outputs/post_charts/. Rerun after every calculation:

    .venv/bin/python scripts/render_post.py [--out PATH] [--final]

Placeholders:
  {{chart:NAME}}            the ```chart block from outputs/post_charts/NAME.json
  {{tax:ARCH:ST}}           |tax_on_military_pay| for a state, as "$1,234"
  {{nstates_plus_dc:ARCH}}  the number of states, as a word, other than DC, whose
                            tax_on_military_pay is $1 or more; fails unless DC's is too
  {{nstates:ARCH}}          the same count; fails if DC's is $1 or more
  {{maxstate:ARCH}} {{maxtax:ARCH}} {{minstate:ARCH}} {{mintax:ARCH}}
                            the state (by name) and amount with the largest and
                            smallest tax_on_military_pay of $1 or more
  {{fedchange:ARCH}}        the federal income tax the pay adds, as "$1,234"
  {{usd:ARCH:ST:COLUMN}}    any dollar column of the results CSV for a state, as
                            "$1,234" (for example federal_agi_military)

Text in [[TODO: ...]] marks a sentence that waits on a source; --final refuses
to render while any remains.
"""

import argparse
import json
import pathlib
import re
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "post" / "template.md"
DEFAULT_OUT = ROOT / "post" / "military-retired-pay-state-taxes-2026.md"

STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    # The post names "the District of Columbia" in full before any state
    # placeholder, so placeholders use the short form.
    "DC": "DC",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

NUMBER_WORDS = [
    "no",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
]


def dollars(x: float) -> str:
    return f"${abs(round(x)):,}"


# The template names these states in its prose and tables. A run that moves a
# state into or out of a set fails the render, so the words never trail the CSV.
EXPECTED = {
    "working_45": {
        "more": {"CA", "CO", "DE", "DC", "ME", "MD", "MT", "OR", "SC", "UT"},
        "less": {"AL", "MO"},
    },
    "retired_67": {
        "more": {"AZ", "DE", "HI", "ID", "IN", "ME", "MT", "NM", "OK", "VT"},
        "less": set(),
    },
}


class Renderer:
    def __init__(self, df: pd.DataFrame, charts: pathlib.Path):
        self.df = df
        self.charts = charts
        for arch, expected in EXPECTED.items():
            tax = self.rows(arch).set_index("state").tax_on_military_pay.round()
            found = {"more": set(tax[tax >= 1].index), "less": set(tax[tax <= -1].index)}
            if found != expected:
                raise ValueError(
                    f"{arch}: the template names {expected}, but the results give "
                    f"{found}; rewrite the template's prose, then update EXPECTED"
                )

    def rows(self, arch: str) -> pd.DataFrame:
        rows = self.df[self.df.archetype == arch]
        if rows.empty:
            raise KeyError(f"unknown archetype {arch!r}")
        return rows

    def taxed(self, arch: str) -> pd.DataFrame:
        rows = self.rows(arch)
        return rows[rows.tax_on_military_pay.round() >= 1]

    def value(self, arch: str, state: str, column: str) -> float:
        row = self.rows(arch)
        row = row[row.state == state]
        if row.empty:
            raise KeyError(f"unknown state {state!r}")
        if column not in row:
            raise KeyError(f"unknown column {column!r}")
        return row[column].iloc[0]

    def tax(self, arch: str, state: str) -> str:
        return dollars(self.value(arch, state, "tax_on_military_pay"))

    def nstates_plus_dc(self, arch: str) -> str:
        taxed = set(self.taxed(arch).state)
        if "DC" not in taxed:
            raise ValueError(f"{arch}: the text names DC, but DC's tax is under $1")
        return NUMBER_WORDS[len(taxed - {"DC"})]

    def nstates(self, arch: str) -> str:
        taxed = set(self.taxed(arch).state)
        if "DC" in taxed:
            raise ValueError(f"{arch}: the text counts states only, but DC's tax is $1 or more")
        return NUMBER_WORDS[len(taxed)]

    def extreme(self, arch: str, largest: bool) -> pd.Series:
        taxed = self.taxed(arch).sort_values("tax_on_military_pay")
        return taxed.iloc[-1] if largest else taxed.iloc[0]

    def fedchange(self, arch: str) -> str:
        rows = self.rows(arch)
        change = (
            rows.federal_income_tax_military - rows.federal_income_tax_none
        ).round()
        if change.nunique() != 1:
            raise ValueError(f"{arch}: federal tax change differs across states")
        return dollars(change.iloc[0])

    def chart(self, name: str) -> str:
        """A ```chart block with each data row and bin on one line, as posts write them."""
        spec = json.loads((self.charts / f"{name}.json").read_text())
        lines = []
        for key, value in spec.items():
            if isinstance(value, list) and all(isinstance(v, dict) for v in value):
                rows = ",\n".join(f"    {json.dumps(v)}" for v in value)
                lines.append(f'  "{key}": [\n{rows}\n  ]')
            else:
                lines.append(f'  "{key}": {json.dumps(value)}')
        body = "{\n" + ",\n".join(lines) + "\n}"
        if json.loads(body) != spec:
            raise ValueError(f"{name}: compact formatting changed the spec")
        return "```chart\n" + body + "\n```"

    def __call__(self, match: re.Match) -> str:
        kind, _, args = match.group(1).partition(":")
        parts = args.split(":") if args else []
        if kind == "chart":
            return self.chart(*parts)
        if kind == "tax":
            return self.tax(*parts)
        if kind == "nstates_plus_dc":
            return self.nstates_plus_dc(*parts)
        if kind == "nstates":
            return self.nstates(*parts)
        if kind in ("maxstate", "minstate"):
            return STATE_NAMES[self.extreme(*parts, kind == "maxstate").state]
        if kind in ("maxtax", "mintax"):
            return dollars(self.extreme(*parts, kind == "maxtax").tax_on_military_pay)
        if kind == "fedchange":
            return self.fedchange(*parts)
        if kind == "usd":
            return dollars(self.value(*parts))
        raise KeyError(f"unknown placeholder {match.group(0)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--final", action="store_true", help="refuse to render with TODOs left"
    )
    args = parser.parse_args()
    df = pd.read_csv(ROOT / "outputs" / "state_military_retirement_2026.csv")
    text = TEMPLATE.read_text()
    todos = re.findall(r"\[\[TODO:.*?\]\]", text, flags=re.S)
    if todos and args.final:
        sys.exit(f"{len(todos)} TODO markers remain; resolve them before --final")
    rendered = re.sub(
        r"\{\{([^{}]+)\}\}", Renderer(df, ROOT / "outputs" / "post_charts"), text
    )
    if "{{" in rendered or "}}" in rendered:
        sys.exit("an unmatched placeholder brace remains")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered)
    print(f"wrote {args.out} ({len(todos)} TODO markers)")


if __name__ == "__main__":
    main()
