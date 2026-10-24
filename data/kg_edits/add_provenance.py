"""
Add to FoodMedKG the same provenance data that data/load_neo4j.py writes
on a full load, without reloading the graph.

The graph described in the paper is the 2025-10-09 dump
(data/neo4j_dump/neo4j.dump), which predates the provenance step of the
loader. This script reuses the loader's own functions, so the result has
the same structure as a fresh load:

    (:Dataset_Metadata)-[:LAST_IMPORTED]->(:Import_Run)-[:USED_SOURCE]->(:Import_Source)
        Import_Run         run_id, pipeline, pipeline_version, started_at_utc, ...
        Import_Source      one per source CSV, with its sha256
    _prov_run_id / _prov_pipeline / _prov_pipeline_version / _prov_source
        on every Food, Composition, Disease, Cooking_Methods,
        Envejecimiento Saludable and Food_Group node and on every
        Affects, Belongs To, Belongs to, Composed By and ES-Food relationship

Timestamps and checksums are computed now. The pipeline recorded is this
script, and the Import_Run also records the dump it was applied to
(base_dump, base_dump_sha256). Adds 9 nodes and 8 relationships.

Dry run by default: prints what would be written and writes nothing.

Usage (from the repo root, with Neo4j running):
    .venv/bin/python data/kg_edits/add_provenance.py            # dry run
    .venv/bin/python data/kg_edits/add_provenance.py --apply    # write
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).parents[1]))
import load_neo4j as loader  # noqa: E402

URI = "bolt://localhost:17687"
AUTH = ("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
BASE_DUMP = Path(__file__).parents[1] / "neo4j_dump" / "neo4j.dump"

loader.PIPELINE_NAME = "data/kg_edits/add_provenance.py"
loader.PIPELINE_VERSION = "2026.10.22"


def main(apply: bool):
    run_id = f"{loader.DATABASE}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    started_at_iso = datetime.now(timezone.utc).isoformat()
    source_checksums = loader.build_source_checksums()
    dump_sha256 = loader.file_sha256(BASE_DUMP)

    print(f"Import_Run {run_id} at {started_at_iso}")
    print(f"  base dump {BASE_DUMP.name}  sha256 {dump_sha256}")
    for src in source_checksums:
        print(f"  source {src['source_key']:<13} sha256 {src['sha256']}")
    if not apply:
        print("\nDry run, nothing written; use --apply.")
        return

    driver = GraphDatabase.driver(URI, auth=AUTH)
    try:
        with driver.session() as s:
            if s.run("MATCH (r:Import_Run) RETURN count(r) AS c").single()["c"]:
                sys.exit("The graph already has an Import_Run; not adding a second one.")
            loader.create_indexes(s)
            loader.create_provenance_structure(s, run_id, started_at_iso, source_checksums)
            s.run(
                "MATCH (r:Import_Run {run_id: $run_id}) SET r.base_dump = $dump, r.base_dump_sha256 = $sha",
                run_id=run_id, dump=str(BASE_DUMP.relative_to(Path(__file__).parents[2])), sha=dump_sha256,
            )
            loader.stamp_provenance(s, run_id)
    finally:
        driver.close()
    print("\nProvenance written.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
