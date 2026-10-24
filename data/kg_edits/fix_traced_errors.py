"""
Fix the errors found while tracing every food–disease edge to its source
statement (see add_association_scope.py and affects_untraced_review.csv).

    1. Food 534 is "Black-eyed pea" in FooDB (Food_Simplificada; its group,
       composition and healthy-ageing nodes all agree) but was named
       "spiny lobster". Renamed to "black-eyed pea"; its cardiovascular
       edge (PMID 28338764, "black-eyed peas") is then correct.
    2. 534 -> cancer is deleted: it was created by copying the source term
       "crustacea" (PMID 28469951) to every food named like a crustacean.
    3. peanut oil -> alzheimer's disease is moved to dermatitis: in the
       source sentence "AD" is atopic dermatitis.
    4. Disease "venereal diseases" is renamed "vascular dementia": its only
       edge (tea) comes from a sentence where "VD" is vascular dementia.
    5. water -> kidney stones is deleted: the source sentence reports no
       relation (neither cause nor treat).
    6. buckwheat flour -> anemia is deleted: the source is fortified "wheat
       flour", matched to buckwheat flour because "wheat" is inside it.

Node counts are unchanged; Affects edges go from 647 to 644. Every edge
and node touched is backed up to fixed_traced_errors.json first, and each
changed element records the fix in `_prov_fix`.

Dry run by default: prints what each step matches, writes nothing.

Usage (from the repo root, with Neo4j running):
    .venv/bin/python data/kg_edits/fix_traced_errors.py            # dry run
    .venv/bin/python data/kg_edits/fix_traced_errors.py --apply    # write
"""

import os
import datetime
import json
import sys
from pathlib import Path

from neo4j import GraphDatabase

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
BACKUP = Path(__file__).parent / "fixed_traced_errors.json"
TODAY = datetime.date.today().isoformat()

BLACK_EYED_PEA = 534
DELETE = [  # (FooDB_id, disease, reason)
    (BLACK_EYED_PEA, "cancer", 'copied from source term "crustacea" because node 534 was misnamed "spiny lobster"'),
    (685, "kidney stones", 'source sentence ("water" / "stones") reports no relation'),
    (825, "anemia", 'source is fortified "wheat flour"; "wheat" matched inside "buckwheat flour"'),
]
MOVE = (974, "alzheimer's disease", "dermatitis", 'source "AD" is atopic dermatitis (peanut oil in skin creams)')
RENAME_DISEASE = ("venereal diseases", "vascular dementia", 'source "VD" is vascular dementia (tea as protective factor)')


def main(apply: bool):
    driver = GraphDatabase.driver(URI, auth=AUTH)
    backup = {"date": TODAY, "edges": [], "nodes": []}
    try:
        with driver.session() as s:
            node = s.run("MATCH (f:Food {FooDB_id: $id}) RETURN properties(f) AS p", id=BLACK_EYED_PEA).single()
            print(f"1. Food {BLACK_EYED_PEA}: {node['p']['Name']!r} -> 'black-eyed pea'")
            backup["nodes"].append({"label": "Food", "FooDB_id": BLACK_EYED_PEA, "properties": node["p"]})

            for fid, disease, reason in DELETE:
                rows = s.run("MATCH (f:Food {FooDB_id: $fid})-[r:Affects]->(d:Disease {Disease: $disease}) "
                             "RETURN properties(r) AS p, f.Name AS food", fid=fid, disease=disease).data()
                print(f"   delete {fid} {rows[0]['food'] if rows else '?'} -> {disease}: {len(rows)} edge(s); {reason}")
                assert len(rows) == 1
                backup["edges"].append({"action": "deleted", "FooDB_id": fid, "disease": disease,
                                        "reason": reason, "properties": rows[0]["p"]})

            fid, old, new, reason = MOVE
            rows = s.run("MATCH (f:Food {FooDB_id: $fid})-[r:Affects]->(d:Disease {Disease: $old}) "
                         "OPTIONAL MATCH (f)-[e:Affects]->(:Disease {Disease: $new}) "
                         "RETURN properties(r) AS p, count(e) AS existing", fid=fid, old=old, new=new).data()
            print(f"   move {fid} -> {old!r} to {new!r}: {len(rows)} edge(s), existing target edges: {rows[0]['existing']}")
            assert len(rows) == 1 and rows[0]["existing"] == 0
            backup["edges"].append({"action": "moved", "FooDB_id": fid, "from": old, "to": new,
                                    "reason": reason, "properties": rows[0]["p"]})

            old, new, reason = RENAME_DISEASE
            deg = s.run("MATCH (d:Disease {Disease: $old}) RETURN properties(d) AS p, COUNT { (d)<-[:Affects]-() } AS n",
                        old=old).single()
            print(f"   rename disease {old!r} -> {new!r}: {deg['n']} edge(s)")
            assert deg["n"] == 1
            backup["nodes"].append({"label": "Disease", "Disease": old, "properties": deg["p"]})

            if not apply:
                print("\nDry run, nothing written; use --apply.")
                return

            BACKUP.write_text(json.dumps(backup, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            s.run("MATCH (f:Food {FooDB_id: $id}) SET f.Name = 'black-eyed pea', "
                  "f._prov_fix = $note", id=BLACK_EYED_PEA,
                  note=f"{TODAY}: renamed from 'spiny lobster'; FooDB {BLACK_EYED_PEA} is Black-eyed pea")
            for fid, disease, _ in DELETE:
                s.run("MATCH (:Food {FooDB_id: $fid})-[r:Affects]->(:Disease {Disease: $disease}) DELETE r",
                      fid=fid, disease=disease)
            fid, old, new, reason = MOVE
            s.run("""
                MATCH (f:Food {FooDB_id: $fid})-[r:Affects]->(:Disease {Disease: $old})
                MATCH (d:Disease {Disease: $new})
                CREATE (f)-[n:Affects]->(d)
                SET n = properties(r), n._prov_fix = $note
                DELETE r
                """, fid=fid, old=old, new=new, note=f"{TODAY}: moved from {old!r}; {reason}")
            old, new, reason = RENAME_DISEASE
            s.run("MATCH (d:Disease {Disease: $old}) SET d.Disease = $new, d._prov_fix = $note",
                  old=old, new=new, note=f"{TODAY}: renamed from {old!r}; {reason}")
    finally:
        driver.close()
    print(f"\nFixes applied; backup in {BACKUP.name}.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
