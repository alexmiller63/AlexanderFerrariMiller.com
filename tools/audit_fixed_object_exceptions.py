#!/usr/bin/env python3
"""Create a compact, human-auditable exception report from the fixed-object identity audit."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
AUDIT = SRC / "generated" / "fixed-object-identity-audit.json"
OUT = SRC / "generated" / "fixed-object-identity-exceptions.json"

SPECIAL_CASE_NOTES = {
    "M24": "Milky Way/star-cloud target; do not force into a conventional compact-object identity.",
    "M40": "Double-star observing target; preserve component identities separately.",
    "M45": "Pleiades target/asterism; preserve target identity and member relationships.",
    "C14": "Double Cluster target; one catalog target relates to NGC 869 and NGC 884.",
    "C33": "Eastern Veil target; Caldwell entry encompasses NGC 6992/6995.",
    "C41": "Hyades target/asterism; preserve cluster/asterism relationship.",
    "C49": "Rosette complex target; preserve the complex relationship to its component NGC entries.",
    "C99": "Coalsack dark-nebula region; preserve region semantics rather than treating it as an ordinary compact object.",
}

def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    candidates = audit.get("candidates", [])
    exceptions = []
    for c in candidates:
        ids = {i.get("namespace") for i in c.get("identifiers", [])}
        if not ids.intersection({"ngc", "ic", "hip", "bayer", "sh2", "variable_star"}):
            row = dict(c)
            row["review_class"] = "no_cross_source_identifier"
            row["database_guidance"] = SPECIAL_CASE_NOTES.get(str(c.get("source_key")), "Review catalog/target semantics before permanent identity assignment.")
            exceptions.append(row)

    result = {
        "schema_version": 1,
        "purpose": "Compact exception report for pre-migration fixed-object identity audit.",
        "source_audit": "Star-Almanack-Repo/generated/fixed-object-identity-audit.json",
        "exception_count": len(exceptions),
        "exceptions": exceptions,
        "permanent_ids_assigned": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Exceptions: {len(exceptions)}")
    print("No fixed_object_id values were assigned.")

if __name__ == "__main__":
    main()
