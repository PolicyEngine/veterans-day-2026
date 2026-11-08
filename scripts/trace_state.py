"""Print a state's intermediate tax variables for one archetype across the three scenarios."""
import sys
from policyengine_us import Simulation
sys.path.insert(0, "scripts")
from state_military_retirement import ARCHETYPES, YEAR, situation, STATES

def main(st, arch_key, extra):
    arch = ARCHETYPES[arch_key]
    i = STATES.index(st.upper())
    s = st.lower()
    names = [f"{s}_agi", f"{s}_taxable_income", f"{s}_income_tax_before_credits",
             f"{s}_non_refundable_credits", f"{s}_refundable_credits", f"{s}_income_tax", "state_income_tax"] + extra
    for scen in ("military", "civilian", "none"):
        sim = Simulation(situation=situation(arch, scen))
        vals = []
        for n in names:
            try:
                v = sim.calculate(n, YEAR)
                # person-level variables: report the head
                v = v[2 * i] if len(v) == 2 * len(STATES) else v[i]
                vals.append(f"{n}={float(v):,.0f}")
            except Exception as e:
                vals.append(f"{n}=ERR({type(e).__name__})")
        print(f"[{st} {arch_key} {scen}] " + "  ".join(vals))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
