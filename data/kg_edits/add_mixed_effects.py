"""
Represent food–disease relations whose sources report both a beneficial and
a harmful association, instead of reducing them to one boolean.

    1. dairy products -> cardiometabolic disease. The only Food-Disease
       Relation dataset tuple marked both is_cause and is_treat ("Dairy
       products contain both beneficial and harmful nutrients in relation to
       cardiometabolic diseases"); it was excluded when the two flags were
       merged. Added on a new group-level Food node "dairy products"
       (FooDB_id 1044, after the existing 1025–1043), which belongs to the
       FooDB group "Milk and milk products" (Group_id 67), added the same way
       as the existing group-level Food_Group nodes (e.g. 51 "Fruits").
    2. apple juice -> asthma and soybean curd -> anemia. Two sources disagree
       on each pair (Alimento_Enfermedad_Completa); the graph keeps one edge
       per pair, so the load kept one value and lost the other source.

On these three edges `Suitable for Disease` is removed and two properties
are set: `effect` = "mixed", and `mixed_evidence`, one entry per source
with what it reports. Citation and Link stay as they were (the dairy edge
cites the Food-Disease Relation dataset). Edges changed are backed up to
mixed_effects_backup.json first; every new element gets the provenance
stamps of the current Import_Run and a `_prov_fix` note.

Adds 2 nodes (Food, Food_Group) and 2 relationships (Belongs To, Affects).

Dry run by default: prints what each step matches, writes nothing.

Usage (from the repo root, with Neo4j running):
    .venv/bin/python data/kg_edits/add_mixed_effects.py            # dry run
    .venv/bin/python data/kg_edits/add_mixed_effects.py --apply    # write
"""

import os
import datetime
import json
import sys
from pathlib import Path

from neo4j import GraphDatabase

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
BACKUP = Path(__file__).parent / "mixed_effects_backup.json"
TODAY = datetime.date.today().isoformat()

NACEV = "Nacev, G. (2021). Food-disease dataset [Data set]. GitHub. https://github.com/gjorgjinac/food-disease-dataset"
NACEV_LINK = "https://github.com/gjorgjinac/food-disease-dataset/blob/main/food_disease_dataset.csv"

DAIRY = {"FooDB_id": 1044, "Name": "dairy products"}
DAIRY_GROUP = {"Group_id": 67, "Group": "Milk and milk products", "Name": "Milk and milk products"}
DAIRY_DISEASE = "cardiometabolic disease"
DAIRY_EVIDENCE = [f"beneficial and harmful: {NACEV} ({NACEV_LINK}): \"Dairy products contain both beneficial "
                  "and harmful nutrients in relation to cardiometabolic diseases.\""]

CONFLICTS = [  # (FooDB_id, disease, mixed_evidence)
    (105, "asthma", [
        "beneficial: Hyson DA. A comprehensive review of apples and apple components and their relationship "
        "to human health. Adv Nutr. 2011;2(5):408-20. (https://pubmed.ncbi.nlm.nih.gov/22332082/), for apple",
        f"harmful: {NACEV} ({NACEV_LINK}), for apple juice",
    ]),
    (85, "anemia", [
        f"beneficial: {NACEV} ({NACEV_LINK}), for glycine max (soybean)",
        "harmful: Goyal et al. (2020). Anemia in Children With Inflammatory Bowel Disease. "
        "(https://pubmed.ncbi.nlm.nih.gov/32947565/), for soy bean",
    ]),
]

STAMP = ("{x}._prov_run_id = r.run_id, {x}._prov_pipeline = r.pipeline, "
         "{x}._prov_pipeline_version = r.pipeline_version, {x}._prov_source = $source, {x}._prov_fix = $note")


def main(apply: bool):
    driver = GraphDatabase.driver(URI, auth=AUTH)
    backup = {"date": TODAY, "edges": []}
    try:
        with driver.session() as s:
            assert not s.run("MATCH (f:Food {FooDB_id: $id}) RETURN f", id=DAIRY["FooDB_id"]).peek(), "dairy node exists"
            assert not s.run("MATCH (g:Food_Group {Group_id: $id}) RETURN g", id=DAIRY_GROUP["Group_id"]).peek(), "group exists"
            assert s.run("MATCH (d:Disease {Disease: $d}) RETURN d", d=DAIRY_DISEASE).peek(), "disease missing"
            print(f"1. + Food {DAIRY} -[Belongs To]-> Food_Group {DAIRY_GROUP}")
            print(f"   + {DAIRY['Name']} -[Affects {{effect: mixed}}]-> {DAIRY_DISEASE}")

            for fid, disease, _ in CONFLICTS:
                rows = s.run("MATCH (f:Food {FooDB_id: $fid})-[r:Affects]->(:Disease {Disease: $d}) "
                             "RETURN f.Name AS food, properties(r) AS p", fid=fid, d=disease).data()
                assert len(rows) == 1
                print(f"2. {rows[0]['food']} -> {disease}: Suitable {rows[0]['p']['Suitable for Disease']} -> mixed")
                backup["edges"].append({"FooDB_id": fid, "disease": disease, "properties": rows[0]["p"]})

            if not apply:
                print("\nDry run, nothing written; use --apply.")
                return

            BACKUP.write_text(json.dumps(backup, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            note = f"{TODAY}: added for the only source tuple marked both cause and treatment (mixed effect)"
            s.run(f"""
                MATCH (r:Import_Run), (d:Disease {{Disease: $disease}})
                CREATE (g:Food_Group) SET g = $group, {STAMP.format(x='g')}
                CREATE (f:Food) SET f = $food, {STAMP.format(x='f')}
                CREATE (f)-[b:`Belongs To`]->(g) SET {STAMP.format(x='b')}
                CREATE (f)-[a:Affects]->(d)
                SET a.Citation = $citation, a.Link = $link, a.effect = 'mixed', a.mixed_evidence = $evidence,
                    a.association_scope = 'group', a.association_scope_note = 'edge on a group-level Food node',
                    {STAMP.format(x='a')}
                """, disease=DAIRY_DISEASE, group=DAIRY_GROUP, food=DAIRY, citation=NACEV, link=NACEV_LINK,
                  evidence=DAIRY_EVIDENCE, source="manual_seed", note=note)
            for fid, disease, evidence in CONFLICTS:
                s.run("""
                    MATCH (:Food {FooDB_id: $fid})-[a:Affects]->(:Disease {Disease: $d})
                    REMOVE a.`Suitable for Disease`
                    SET a.effect = 'mixed', a.mixed_evidence = $evidence, a._prov_fix = $note
                    """, fid=fid, d=disease, evidence=evidence,
                      note=f"{TODAY}: sources disagree; was stored as a single boolean, now mixed with both sources")
    finally:
        driver.close()
    print(f"\nMixed effects written; backup in {BACKUP.name}.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
