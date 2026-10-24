"""
Write human-consensus grades from the survey to FoodMedKG.

Reads survey/analysis/results/consensus_grades.csv (run
survey/analysis/run_all.py first) and sets, on every evaluated element:

    consensus_score    share of Agree among decisive answers (0–1)
    consensus_grade    strong / moderate / contested / rejected
    consensus_n        number of annotators who rated it

- Food–disease:  properties on the (:Food)-[:Affects]->(:Disease) edge
- Aging:         <component>_consensus_score / _grade / _n on the
                 (:`Envejecimiento Saludable`) node(s) of that food whose
                 <component>_level equals the level the survey item stated
                 (a food can have several variant nodes; the evaluated
                 statement holds for every node with that level)
- Cooking:       properties on the (:Cooking_Methods) node

Elements that were not evaluated are left untouched (no property).

Dry run by default: prints what each row matches and writes nothing.

Usage (from the repo root, with Neo4j running):
    healthyfood_env/bin/python data/kg_edits/add_consensus.py            # dry run
    healthyfood_env/bin/python data/kg_edits/add_consensus.py --apply    # write
"""

import os
import sys
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
GRADES_CSV = Path(__file__).parents[2] / "survey" / "analysis" / "results" / "consensus_grades.csv"

# Survey food name -> graph Food.Name, where they differ. Checked against the
# graph; every other food–disease item matches by case-insensitive name.
FOOD_NAME_MAP = {
    "garlic": "crushed garlic",
    "tomato": "tomato fruit",
    "oats": "oat",
    "green tea": "green tea from camellia sinensis",
    "turmeric": "curcuma longa",
    "chickpeas": "chickpea",
    "olive oil": "olive oil)",
    "ginger": "ginger root",
    "cinnamon": "cinnamomum",
    "almonds": "almond",
    "coffee": "coffee consumption",
    "cow's milk": "cow's milk protein",  # survey item I068 was worded "cow's milk"
}

DISEASE_MATCH = """
MATCH (f:Food)-[r:Affects]->(d:Disease {Disease: $disease})
WHERE toLower(f.Name) = toLower($food)
RETURN elementId(r) AS id
"""
AGING_MATCH = """
MATCH (h:`Envejecimiento Saludable`)
WHERE toLower(h.Name) = toLower($food) AND h[$level_key] = $level
RETURN elementId(h) AS id
"""
COOKING_MATCH = "MATCH (m:Cooking_Methods {Cooking_Method: $method}) RETURN elementId(m) AS id"


def main(apply: bool):
    grades = pd.read_csv(GRADES_CSV)
    driver = GraphDatabase.driver(URI, auth=AUTH)
    problems = 0
    with driver.session() as s:
        for r in grades.itertuples():
            props = {"consensus_score": float(r.consensus_score), "consensus_grade": r.consensus_grade,
                     "consensus_n": int(r.n_agree + r.n_not_sure + r.n_disagree)}
            if r.type == "disease":
                food = FOOD_NAME_MAP.get(r.food, r.food)
                ids = [x["id"] for x in s.run(DISEASE_MATCH, food=food, disease=r.target)]
                write = "MATCH ()-[e]->() WHERE elementId(e) = $id SET e += $props"
            elif r.type == "aging":
                ids = [x["id"] for x in s.run(AGING_MATCH, food=r.food, level_key=f"{r.target}_level",
                                              level=int(r.aging_level))]
                props = {f"{r.target}_{k}": v for k, v in props.items()}
                write = "MATCH (n) WHERE elementId(n) = $id SET n += $props"
            else:
                ids = [x["id"] for x in s.run(COOKING_MATCH, method=r.target)]
                write = "MATCH (n) WHERE elementId(n) = $id SET n += $props"

            # edges and cooking nodes must match exactly once; aging may match several variant nodes
            ok = len(ids) == 1 or (r.type == "aging" and len(ids) > 1)
            status = f"OK x{len(ids)}" if ok else f"MATCHED {len(ids)} — skipped"
            print(f"[{status}] {r.element}: {r.food} – {r.target} -> {props}")
            if not ok:
                problems += 1
                continue
            if apply:
                for element_id in ids:
                    s.run(write, id=element_id, props=props)
    driver.close()
    print(f"\n{len(grades) - problems}/{len(grades)} evaluated relations matched"
          + (" and written." if apply else " (dry run, nothing written; use --apply)."))


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
