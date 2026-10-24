"""
Add Disease Ontology identifiers to FoodMedKG's Disease nodes.

The paper's graph (the 2025-10-09 dump) keys Disease nodes by name only.
The merged food–disease table (Alimento_Enfermedad_Completa) carries the
DOID that the Food-Disease Relation dataset assigns to 50 of its 147
diseases; this script sets it as `DOID` on the matching node, the same
property data/load_neo4j.py writes (enrich_disease_doid).

Nodes are matched on the disease name. Diseases with no DOID in the source
are left untouched, as are names that match no node (e.g. diseases renamed
by fix_traced_errors.py, whose old DOID would no longer apply).

Dry run by default: prints the matching, writes nothing.

Usage (from the repo root, with Neo4j running):
    .venv/bin/python data/kg_edits/add_disease_doid.py            # dry run
    .venv/bin/python data/kg_edits/add_disease_doid.py --apply    # write
"""

import os
import sys
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
COMPLETA = (Path(__file__).parents[1] / "mongoDB" / "extracted" / "MongoDB" / "Colecciones_Finales"
            / "Colecciones_Finales.Alimento_Enfermedad_Completa.csv")

WRITE = """
UNWIND $rows AS row
MATCH (d:Disease {Disease: row.disease})
SET d.DOID = row.doid
"""


def main(apply: bool):
    src = pd.read_csv(COMPLETA, dtype=str).dropna(subset=["DOID"])
    doids = src.groupby("Disease")["DOID"].agg(lambda s: sorted(set(s.str.strip())))
    conflicting = doids[doids.map(len) > 1]
    if len(conflicting):
        sys.exit(f"Diseases with more than one DOID in the source: {conflicting.to_dict()}")

    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        with driver.session() as s:
            graph = {r["d"] for r in s.run("MATCH (d:Disease) RETURN d.Disease AS d")}
            rows = [{"disease": d, "doid": v[0]} for d, v in doids.items() if d in graph]
            missing = sorted(set(doids.index) - graph)
            print(f"{len(doids)} diseases with a DOID in the source; {len(rows)} match a node "
                  f"(of {len(graph)} Disease nodes); not in the graph: {missing}")
            if apply:
                s.run(WRITE, rows=rows)
    finally:
        driver.close()
    print("\nDOIDs written." if apply else "\nDry run, nothing written; use --apply.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
