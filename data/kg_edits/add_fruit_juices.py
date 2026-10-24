"""
Add the healthy-ageing category "Fruit juices", lost when the graph was built.

The healthy-ageing study was digitised as 61 food items, but the graph has
59 categories. "Fruit juices" was dropped because its FooDB mapping
(ES_Alterada.ES_FooDB) put the FooDB *food* ids 788, 851, 959 and 960 in
the *group* id field, so it matched no group. "Starchy Vegetables" had no
mapping at all and stays out.

This script creates one (:`Envejecimiento Saludable`) node per food, with
the same properties as the existing nodes: Name, FooDB_ID, Food (the
category), _id, the six decimal values and their 0–4 levels. Levels use
the rule of the existing nodes (each aspect's min–max range over the graph
split into 5 equal parts), not the levels stored in ES_Rango, which use a
different scale. Each node gets the provenance stamps of the current
Import_Run and a `_prov_fix` note. None of the four foods is a Food node,
so no ES-Food relationship is created.

Dry run by default: prints the nodes, writes nothing.

Usage (from the repo root, with Neo4j running):
    .venv/bin/python data/kg_edits/add_fruit_juices.py            # dry run
    .venv/bin/python data/kg_edits/add_fruit_juices.py --apply    # write
"""

import os
import datetime
import sys
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
BASE = Path(__file__).parents[1] / "mongoDB" / "extracted" / "MongoDB"
ES_RANGO = BASE / "ES_Alterada" / "ES_Alterada.ES_Rango.csv"
FOODS = BASE / "Colecciones_Auxiliares" / "Colecciones_Auxiliares.Food_Simplificada.csv"
CATEGORY = "Fruit juices"
FOODB_IDS = [788, 851, 959, 960]  # from ES_Alterada.ES_FooDB, where they sit in the group id field
TODAY = datetime.date.today().isoformat()

ASPECTS = ["Healthy Aging", "Intact Cognitive Function", "Intact physical function",
           "Intact mental health", "Free From Chronic Disease", "Survived For 70 Years Of Age"]

CREATE = """
MATCH (r:Import_Run)
UNWIND $rows AS row
CREATE (h:`Envejecimiento Saludable`)
SET h = row.props,
    h._prov_run_id = r.run_id, h._prov_pipeline = r.pipeline,
    h._prov_pipeline_version = r.pipeline_version, h._prov_source = 'csv:ES_Alterada',
    h._prov_fix = $note
"""


def main(apply: bool):
    rango = pd.read_csv(ES_RANGO, dtype=str)
    src = rango[rango["Food"] == CATEGORY].iloc[0]
    values = {a: float(src[a].replace(",", ".")) for a in ASPECTS}
    names = pd.read_csv(FOODS, dtype=str).set_index("FooDB_ID")["Name"]

    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        with driver.session() as s:
            if s.run("MATCH (h:`Envejecimiento Saludable` {Food: $c}) RETURN count(h) AS n", c=CATEGORY).single()["n"]:
                sys.exit(f"The graph already has {CATEGORY!r} nodes.")
            levels = {}
            for a in ASPECTS:
                lo, hi = s.run(f"MATCH (h:`Envejecimiento Saludable`) RETURN min(h.`{a}`) AS lo, max(h.`{a}`) AS hi").single()
                assert lo <= values[a] <= hi, f"{a}: {values[a]} outside the graph range {lo}–{hi}"
                levels[f"{a}_level"] = min(int((values[a] - lo) / (hi - lo) * 5), 4)
            print(f"{CATEGORY}: values {values}\n  levels {levels}")

            rows = []
            for fid in FOODB_IDS:
                props = {"Name": names[str(fid)], "FooDB_ID": fid, "Food": CATEGORY,
                         "_id": f"{src['_id']}-{fid}", **values, **levels}
                rows.append({"props": props})
                print(f"  + {fid} {props['Name']}")
            if apply:
                s.run(CREATE, rows=rows, note=f"{TODAY}: added; category '{CATEGORY}' was dropped at build time "
                                              f"because its FooDB food ids were stored as group ids")
    finally:
        driver.close()
    print("\nNodes created." if apply else "\nDry run, nothing written; use --apply.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
