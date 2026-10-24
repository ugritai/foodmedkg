"""
Fix the unit label of energy in the Composition nodes.

FooDB gives energy in kJ/100 g, but data/3_FooDB_Pivoted.py labels each
value with the unit of the original record: "kcal/100 g" (USDA records),
"mg/100 g" (DTU records), and values above 1000 were divided by 1000 and
labelled "g/100 g". The numbers are kJ in every case, e.g. green leaf
lettuce 62 kJ = 15 kcal (USDA: 15 kcal), raw strawberries 136 kJ = 33 kcal
(USDA: 32 kcal), and the same food has similar values in USDA and DTU
(romaine lettuce 72 and 69).

This script rewrites the "Energy" entry of `constituents` as "<value> kJ/100 g"
(multiplying by 1000 the values labelled g/100 g). No other constituent is
changed. The previous value of every changed node is backed up to
energy_units_backup.json first, and each changed node records the fix in
`_prov_fix`.

Dry run by default: prints what would change, writes nothing.

Usage (from the repo root, with Neo4j running):
    .venv/bin/python data/kg_edits/fix_energy_units.py            # dry run
    .venv/bin/python data/kg_edits/fix_energy_units.py --apply    # write
"""

import os
import datetime
import json
import sys
from collections import Counter
from pathlib import Path

from neo4j import GraphDatabase

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
BACKUP = Path(__file__).parent / "energy_units_backup.json"
TODAY = datetime.date.today().isoformat()
NOTE = (f"{TODAY}: Energy relabelled as kJ/100 g; FooDB values are kJ but were "
        "labelled with the unit of the original record (kcal or mg; g above 1000)")
FACTOR = {"kcal/100 g": 1, "mg/100 g": 1, "g/100 g": 1000, "kJ/100 g": 1}


def fixed_energy(value: str) -> str:
    num, unit = value.split(" ", 1)
    kj = round(float(num) * FACTOR[unit], 3)
    return f"{kj} kJ/100 g"


def main(apply: bool):
    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        with driver.session() as s:
            rows = s.run("MATCH (c:Composition) WHERE c.constituents CONTAINS '\"Energy\"' "
                         "RETURN elementId(c) AS eid, c.id AS id, c.food_name AS name, "
                         "c.constituents AS cons").data()
            updates, backup, units = [], [], Counter()
            for r in rows:
                cons = json.loads(r["cons"])
                # Re-serialising must give back the stored string, so that only Energy changes.
                assert json.dumps(cons, ensure_ascii=False) == r["cons"], r["id"]
                old = cons["Energy"]
                unit = old.split(" ", 1)[1]
                assert unit in FACTOR, (r["id"], old)
                units[unit] += 1
                if unit == "kJ/100 g":
                    continue
                cons["Energy"] = fixed_energy(old)
                updates.append({"eid": r["eid"], "cons": json.dumps(cons, ensure_ascii=False)})
                backup.append({"id": r["id"], "food_name": r["name"], "Energy": old, "constituents": r["cons"]})

            print(f"Composition nodes with Energy: {len(rows)}; labels found: {dict(units)}")
            print(f"To change: {len(updates)}")
            for b in backup[:3] + [b for b in backup if b["Energy"].endswith(" g/100 g")][:2]:
                print(f"   {b['food_name']}: {b['Energy']!r} -> {fixed_energy(b['Energy'])!r}")

            if not apply:
                print("\nDry run, nothing written; use --apply.")
                return

            BACKUP.write_text(json.dumps({"date": TODAY, "nodes": backup}, indent=1, ensure_ascii=False),
                              encoding="utf-8")
            s.run("UNWIND $rows AS row MATCH (c) WHERE elementId(c) = row.eid "
                  "SET c.constituents = row.cons, c._prov_fix = $note", rows=updates, note=NOTE)
    finally:
        driver.close()
    print(f"\nFix applied to {len(updates)} nodes; backup in {BACKUP.name}.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
