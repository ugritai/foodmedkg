"""
Add the healthy-ageing decimal values to FoodMedKG.

The (:`Envejecimiento Saludable`) nodes of the paper's graph (the
2025-10-09 dump) store only the 0–4 level of each aspect
(`Healthy Aging_level`, ...), not the value the level was derived from.
This script adds those values as numbers, under the same property names
data/load_neo4j.py uses:

    `Healthy Aging`, `Intact Cognitive Function`, `Intact physical function`,
    `Intact mental health`, `Free From Chronic Disease`,
    `Survived For 70 Years Of Age`

Values come from Colecciones_Finales.ES_Final.csv ("1,13" -> 1.13). The
CSV's own *_level columns are not used: they only span 0–3 and disagree
with the graph. Nodes are matched on (FooDB_ID, Food), which is unique on
both sides. Before writing, every value is checked against the node's
existing level, using the binning in data/data_preparation.txt (each
aspect's min–max range split into 5 equal parts, 0 = bad, 4 = good).

Dry run by default: reports the matching and the check, writes nothing.

Usage (from the repo root, with Neo4j running):
    .venv/bin/python data/kg_edits/add_aging_values.py            # dry run
    .venv/bin/python data/kg_edits/add_aging_values.py --apply    # write
"""

import os
import sys
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
ES_CSV = (Path(__file__).parents[1] / "mongoDB" / "extracted" / "MongoDB" / "Colecciones_Finales"
          / "Colecciones_Finales.ES_Final.csv")

ASPECTS = ["Healthy Aging", "Intact Cognitive Function", "Intact physical function",
           "Intact mental health", "Free From Chronic Disease", "Survived For 70 Years Of Age"]

GRAPH_NODES = ("MATCH (h:`Envejecimiento Saludable`) RETURN elementId(h) AS id, toString(h.FooDB_ID) AS FooDB_ID, "
               "h.Food AS Food, " + ", ".join(f"h.`{a}_level` AS `{a}_level`" for a in ASPECTS))
WRITE = """
UNWIND $rows AS row
MATCH (h) WHERE elementId(h) = row.id
SET h += row.props
"""


def level_of(values: pd.Series) -> pd.Series:
    """0–4 bin of each value within the aspect's min–max range (5 equal parts)."""
    lo, hi = values.min(), values.max()
    return ((values - lo) / (hi - lo) * 5).clip(upper=4.999).astype(int)


def main(apply: bool):
    csv = pd.read_csv(ES_CSV, dtype=str)
    for a in ASPECTS:
        csv[a] = csv[a].str.replace(",", ".").astype(float)

    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        with driver.session() as s:
            graph = pd.DataFrame(s.run(GRAPH_NODES).data())
            m = graph.merge(csv[["FooDB_ID", "Food", *ASPECTS]], on=["FooDB_ID", "Food"], how="left",
                            validate="one_to_one", indicator=True)
            unmatched = int((m["_merge"] != "both").sum())
            print(f"{len(graph)} nodes, {len(graph) - unmatched} matched to {ES_CSV.name}, {unmatched} unmatched")

            mismatches = 0
            for a in ASPECTS:
                bad = int((level_of(m[a]) != m[f"{a}_level"]).sum())
                mismatches += bad
                print(f"  {a:<30} {m[a].min():.2f}–{m[a].max():.2f}   value/level disagreements: {bad}")
            if unmatched or mismatches or m[ASPECTS].isna().any().any():
                sys.exit("Not writing: some nodes are unmatched, missing a value, or disagree with their level.")

            if apply:
                rows = [{"id": r["id"], "props": {a: float(r[a]) for a in ASPECTS}} for _, r in m.iterrows()]
                for i in range(0, len(rows), 500):
                    s.run(WRITE, rows=rows[i:i + 500])
    finally:
        driver.close()
    print("\nValues written." if apply else "\nDry run, nothing written; use --apply.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
