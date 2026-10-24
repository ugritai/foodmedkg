"""
Mark on every food–disease edge whether the association was reported for
that food or derived from a broader food group.

Reads data/kg_edits/affects_scope.csv (one row per edge) and sets, on each
(:Food)-[:Affects]->(:Disease) edge:

    association_scope       food                 the source statement names this food
                            derived_from_group   the source names a broader term (e.g. "soy",
                                                 "red meats", a food-group meta-analysis) and
                                                 the edge was copied to this individual food
                            group                the statement is about a group and is stored
                                                 on a group-level Food node (FooDB_id 1025–1043)
                            untraced             no matching statement found in the cited source
                                                 or in the FDR/FAALD exports
    association_scope_note  why the edge got that value

The CSV was built by tracing each edge back to the FDR/FAALD exports and
the raw Food-Disease dataset, with a few manual decisions; edit it to
refine a label and re-run. Edges are matched on (FooDB_id, disease, link).

Edges left "untraced" there are reviewed in affects_untraced_review.csv:
its `decision` column overrides the scope (and `why` the note) of the
matching edge, so a review only needs that column edited.

Dry run by default: reports the matching, writes nothing.

Usage (from the repo root, with Neo4j running):
    .venv/bin/python data/kg_edits/add_association_scope.py            # dry run
    .venv/bin/python data/kg_edits/add_association_scope.py --apply    # write
"""

import os
import sys
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
SCOPE_CSV = Path(__file__).parent / "affects_scope.csv"
REVIEW_CSV = Path(__file__).parent / "affects_untraced_review.csv"
SCOPES = {"food", "derived_from_group", "group", "untraced"}

EDGES = """
MATCH (f:Food)-[r:Affects]->(d:Disease)
RETURN elementId(r) AS id, f.FooDB_id AS fid, d.Disease AS disease, r.Link AS link
"""
WRITE = """
UNWIND $rows AS row
MATCH ()-[r]->() WHERE elementId(r) = row.id
SET r.association_scope = row.scope, r.association_scope_note = row.note
"""


def main(apply: bool):
    scopes = pd.read_csv(SCOPE_CSV)
    if REVIEW_CSV.exists():
        review = pd.read_csv(REVIEW_CSV)[["fid", "disease", "link", "decision", "why"]]
        scopes = scopes.merge(review, on=["fid", "disease", "link"], how="left", validate="one_to_one")
        reviewed = scopes["decision"].notna()
        scopes.loc[reviewed, "scope"] = scopes.loc[reviewed, "decision"]
        scopes.loc[reviewed, "reason"] = scopes.loc[reviewed, "why"]
        print(f"{reviewed.sum()} edges take their scope from {REVIEW_CSV.name}")
    bad = set(scopes["scope"]) - SCOPES
    if bad:
        sys.exit(f"Unknown scope values in {SCOPE_CSV.name}: {sorted(bad)}")

    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        with driver.session() as s:
            edges = pd.DataFrame(s.run(EDGES).data())
            m = edges.merge(scopes, on=["fid", "disease", "link"], how="outer", validate="one_to_one", indicator=True)
            missing, extra = (m["_merge"] == "left_only").sum(), (m["_merge"] == "right_only").sum()
            print(f"{len(edges)} Affects edges, {len(scopes)} CSV rows: "
                  f"{(m['_merge'] == 'both').sum()} matched, {missing} edges without a row, {extra} rows without an edge")
            print("  " + ", ".join(f"{k}: {v}" for k, v in m["scope"].value_counts().items()))
            if missing or extra:
                sys.exit("Not writing: every edge needs exactly one row.")

            if apply:
                rows = [{"id": r.id, "scope": r.scope, "note": r.reason} for r in m.itertuples()]
                s.run(WRITE, rows=rows)
    finally:
        driver.close()
    print("\nScope written." if apply else "\nDry run, nothing written; use --apply.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
