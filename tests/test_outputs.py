"""Checks that the committed outputs, charts and post agree with each other.

They read only files in this repository, so they run without PolicyEngine-US.
Each one states a property that holds for every state and both couples.
"""

import json
import pathlib
import re

import sys

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from post_charts import STATE_NAMES  # noqa: E402
RESULTS = pd.read_csv(ROOT / "outputs" / "state_military_retirement_2026.csv")
META = json.loads((ROOT / "outputs" / "run_metadata.json").read_text())
CHARTS = ROOT / "outputs" / "post_charts"
POST = (ROOT / "post" / "military-retired-pay-state-taxes-2026.md").read_text()

NO_INCOME_TAX = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}
ARCHETYPES = sorted(META["archetypes"])


def test_every_state_and_dc_runs_once_per_couple():
    for arch in ARCHETYPES:
        states = RESULTS[RESULTS.archetype == arch].state
        assert len(states) == 51 and states.is_unique


def test_tax_on_the_pay_is_the_difference_between_the_two_runs():
    diff = RESULTS.state_income_tax_military - RESULTS.state_income_tax_none
    assert (diff - RESULTS.tax_on_military_pay).abs().max() < 0.011


def test_military_break_is_the_gap_to_a_private_pension():
    gap = RESULTS.state_income_tax_civilian - RESULTS.state_income_tax_military
    assert (gap - RESULTS.military_break).abs().max() < 0.011


def test_states_without_a_broad_income_tax_levy_nothing():
    rows = RESULTS[RESULTS.state.isin(NO_INCOME_TAX)]
    tax = rows[[c for c in rows if c.startswith("state_income_tax_")]]
    assert (tax == 0).all().all()


def test_federal_results_do_not_depend_on_the_state():
    # Each couple has the same federal return wherever it lives, except that
    # Alaska's Permanent Fund Dividend adds to federal income there.
    rows = RESULTS[RESULTS.state != "AK"]
    for arch in ARCHETYPES:
        sub = rows[rows.archetype == arch]
        for column in ("federal_agi_military", "federal_income_tax_military"):
            assert sub[column].nunique() == 1, (arch, column)


@pytest.mark.parametrize("arch", ARCHETYPES)
def test_map_shows_the_csv_value_for_every_state_with_an_income_tax(arch):
    spec = json.loads((CHARTS / f"map_{arch}.json").read_text())
    shown = {row["state"]: row["tax"] for row in spec["data"]}
    rows = RESULTS[RESULTS.archetype == arch].set_index("state")
    assert set(shown) == set(rows.index) - NO_INCOME_TAX
    for state, tax in shown.items():
        assert tax == round(float(rows.tax_on_military_pay[state]))


@pytest.mark.parametrize("arch", ARCHETYPES)
def test_bar_chart_lists_exactly_the_states_where_the_couple_owes_more(arch):
    spec = json.loads((CHARTS / f"bar_{arch}.json").read_text())
    rows = RESULTS[RESULTS.archetype == arch].set_index("state")
    owes_more = rows[rows.tax_on_military_pay >= 1]
    # The bars name each state in full; map the names back to the CSV's codes.
    assert len(set(STATE_NAMES.values())) == len(STATE_NAMES) == 51
    code = {name: abbr for abbr, name in STATE_NAMES.items()}
    assert [code[r["state"]] for r in spec["data"]] == list(
        owes_more.sort_values("tax_on_military_pay", ascending=False).index
    )
    for row in spec["data"]:
        assert row["tax"] == round(float(rows.tax_on_military_pay[code[row["state"]]]))


def test_post_embeds_the_current_chart_specs():
    blocks = [json.loads(b) for b in re.findall(r"```chart\n(.*?)\n```", POST, re.S)]
    assert blocks, "the post has no chart blocks"
    current = [json.loads(p.read_text()) for p in sorted(CHARTS.glob("*.json"))]
    for block in blocks:
        assert block in current


def test_post_has_no_unfilled_markers():
    assert "[[TODO" not in POST and "{{" not in POST and "}}" not in POST
