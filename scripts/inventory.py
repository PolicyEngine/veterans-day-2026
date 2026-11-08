"""Inventory every veteran- and military-related rule in the installed policyengine-us.

Scans the package's parameter YAML and variable source for references to veteran
status, VA benefits, military retirement pay and active-duty military pay, and
writes one row per file to outputs/inventory_raw.csv. Run with the pinned
policyengine-us from requirements.txt so the inventory matches the calculations.
"""

import csv
import json
import pathlib
import re
import sys

import policyengine_us
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from model_source import model_source  # noqa: E402

ROOT = pathlib.Path(policyengine_us.__file__).parent
SOURCE = model_source()
OUT = pathlib.Path(__file__).resolve().parents[1] / "outputs"

# Input variables that carry veteran or military status or income.
KEYS = {
    "veterans_benefits": "VA benefits (income)",
    "is_veteran": "veteran status",
    "is_permanently_disabled_veteran": "disabled veteran status",
    "is_fully_disabled_service_connected_veteran": "disabled veteran status",
    "is_surviving_spouse_of_disabled_veteran": "disabled veteran survivor",
    "is_surviving_child_of_disabled_veteran": "disabled veteran survivor",
    "military_disabled_head": "disabled veteran status",
    "military_disabled_spouse": "disabled veteran status",
    "military_retirement_pay": "military retirement pay",
    "military_retirement_pay_survivors": "military survivor annuity",
    "years_in_military": "years of service",
    "is_military": "active-duty status",
    "military_basic_pay": "active-duty pay",
    "military_service_income": "active-duty pay",
    "military_retirement_income": "military retirement pay",
    "has_va_health_coverage_at_interview": "VA health coverage",
    "has_tricare_health_coverage_at_interview": "TRICARE coverage",
    "has_champva_health_coverage_at_interview": "CHAMPVA coverage",
    "is_snap_alien_military_connected": "military connection (SNAP)",
    "il_cta_military_service_pass_eligible": "military service pass (Chicago transit)",
    "me_property_tax_fairness_credit_veterans_cap": "veterans cap (Maine credit)",
    "ky_military_personal_tax_credits": "military personal credit (Kentucky)",
}
WORD = re.compile(r"\b(" + "|".join(map(re.escape, KEYS)) + r")\b")
FREE = re.compile(r"veteran|military|armed forces|uniformed services", re.I)


def jurisdiction(rel: str) -> str:
    parts = rel.split("/")
    if "states" in parts:
        return parts[parts.index("states") + 1].upper()
    if "territories" in parts:
        return parts[parts.index("territories") + 1].upper()
    if "local" in parts:
        i = parts.index("local")
        return "local:" + "/".join(parts[i + 1 : i + 3])
    if "gov" in parts:
        return "federal:" + parts[parts.index("gov") + 1]
    return "household"


def scan_parameters():
    rows = []
    for path in sorted((ROOT / "parameters").rglob("*.yaml")):
        text = path.read_text()
        if not (WORD.search(text) or FREE.search(text)):
            continue
        rel = str(path.relative_to(ROOT))
        try:
            data = yaml.load(text, Loader=yaml.BaseLoader) or {}
        except (yaml.YAMLError, ValueError):
            data = {}
        meta = data.get("metadata", {}) if isinstance(data, dict) else {}
        refs = meta.get("reference") or data.get("reference") or []
        if isinstance(refs, dict):
            refs = [refs]
        rows.append(
            {
                "kind": "parameter",
                "jurisdiction": jurisdiction(rel),
                "path": rel,
                "inputs_named": ";".join(sorted(set(WORD.findall(text)))),
                "mentions_text": bool(FREE.search(text)),
                "label": meta.get("label", "") if isinstance(meta, dict) else "",
                "description": (
                    data.get("description", "") if isinstance(data, dict) else ""
                )[:300],
                "references": " | ".join(
                    r.get("href", "") for r in refs if isinstance(r, dict)
                )[:500],
            }
        )
    return rows


def scan_variables():
    rows = []
    for path in sorted((ROOT / "variables").rglob("*.py")):
        text = path.read_text()
        if not (WORD.search(text) or FREE.search(text)):
            continue
        rel = str(path.relative_to(ROOT))
        label = re.search(r'label\s*=\s*\(?\s*"([^"]+)"', text)
        refs = re.findall(r'"(https?://[^"]+)"', text)
        rows.append(
            {
                "kind": "variable",
                "jurisdiction": jurisdiction(rel),
                "path": rel,
                "inputs_named": ";".join(sorted(set(WORD.findall(text)))),
                "mentions_text": bool(FREE.search(text)),
                "label": label.group(1) if label else "",
                "description": "",
                "references": " | ".join(refs)[:500],
            }
        )
    return rows


def main():
    rows = scan_parameters() + scan_variables()
    rows = [r for r in rows if "/tests/" not in r["path"]]
    OUT.mkdir(exist_ok=True)
    with open(OUT / "inventory_raw.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    named = [r for r in rows if r["inputs_named"]]
    summary = {
        **SOURCE,
        "files_mentioning_veterans_or_military": len(rows),
        "files_naming_an_input": len(named),
        "inputs_searched": len(KEYS),
        "files_by_input": {
            k: sum(k in r["inputs_named"].split(";") for r in rows) for k in KEYS
        },
    }
    (OUT / "inventory_meta.json").write_text(json.dumps(summary, indent=2))
    print(
        f"policyengine-us {SOURCE['policyengine_us']}: {len(rows)} files mention veterans "
        f"or the military; {len(named)} name one of the {len(KEYS)} veteran/military inputs"
    )


if __name__ == "__main__":
    main()
