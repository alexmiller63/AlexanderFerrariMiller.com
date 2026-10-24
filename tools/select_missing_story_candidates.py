#!/usr/bin/env python3
"""Select genuinely missing curated stories without paid API calls."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
STORY_DIRS = ("alpha-stars", "beta-stars", "special-stars", "messier", "caldwell", "finest")


def curated_scope():
    """Use the persisted six-collection coverage, never the entire star registry."""
    coverage = json.loads((ROOT / "database/fixed-sky-annual-coverage.json").read_text())
    allowed = {"expanded-bayer", "bright-star", "special-star", "messier", "caldwell", "finest_ngc"}
    ids, unresolved = set(), {}
    for year in (2025, 2026, 2027):
        rows = [row for row in coverage["coverage"] if row["coverage_year"] == year]
        if len(rows) != 1:
            raise RuntimeError(f"Missing or duplicate curated coverage for {year}")
        for item in rows[0]["objects"]:
            if item["source"] not in allowed:
                raise RuntimeError(f"Unexpected collection: {item['source']}")
            ident = item.get("fixed_object_id")
            if ident is None:
                unresolved[(item["source"], item["key"])] = {
                    "collection": item["source"], "key": item["key"],
                    "reason": "No single permanent object identity in annual coverage"}
            else:
                ids.add(int(ident))
    return ids, list(unresolved.values())


def registry_identity(obj):
    # Use an astronomical identifier, never a display name or CSV row number.
    for namespace in ("hip", "ngc", "ic", "messier", "hd", "gaia_dr3", "bayer", "sh2"):
        for ident in obj.get("identifiers", []):
            if ident["namespace"] == namespace:
                value = str(ident["value"])
                query = ({"messier": "M " + value.lstrip("Mm"),
                          "gaia_dr3": "Gaia DR3 " + value,
                          "bayer": value, "sh2": "Sh 2-" + value}.get(namespace)
                         or namespace.upper() + " " + value)
                return dict(namespace=namespace, value=value), query
    raise RuntimeError(f"No supported research identifier for object {obj['fixed_object_id']}")

def candidates(limit=10, resume_interrupted=False):
    objects = json.loads((ROOT / "database/fixed-objects.json").read_text())["fixed_objects"]
    curated_ids, _ = curated_scope()
    registry = json.loads((ROOT / "database/fixed-object-registry.json").read_text())["fixed_objects"]
    active = {int(o["fixed_object_id"]): o for o in registry if o.get("status") == "active"}
    if curated_ids - set(active):
        raise RuntimeError("Curated coverage contains inactive or unknown object IDs")
    existing = {int(p.stem) for folder in STORY_DIRS for p in (ROOT / "stories" / folder).glob("*.md") if p.stem.isdigit()}
    saved = ROOT / "generated/luna-pilot"
    # Any saved work or checkpoint reserves its permanent object ID.
    # Do not reselect interrupted research, evidence, audit or paid stages.
    resumable = set()
    if resume_interrupted and saved.exists():
        for evidence in saved.glob("*.evidence.json"):
            ident = evidence.name.split(".")[0]
            if (ident.isdigit() and not (saved / (ident + ".md")).exists()
                    and not (saved / (ident + ".failure.json")).exists()
                    and (list(saved.glob(ident + ".*.stage.txt"))
                         or list(saved.glob(ident + ".*.response.json")))):
                resumable.add(int(ident))
    if saved.exists():
        for p in saved.iterdir():
            if p.is_file():
                match = re.match(r"^(\d+)(?:\.|$)", p.name)
                if match and int(match.group(1)) not in resumable:
                    existing.add(int(match.group(1)))
    existing.update(int(p.stem) for p in saved.glob("*.md") if p.stem.isdigit())
    # Completed replacement drafts reserve the same permanent object identity.
    existing.update(int(p.stem) for p in (saved / "repairs").glob("*.md") if p.stem.isdigit())
    # Do not repeat any previous pilot candidate until its status has been reconciled.
    previous = ROOT / "research/luna-pilot-candidates.json"
    if previous.exists():
        for task in json.loads(previous.read_text()):
            hip = re.search(r"Registry identity:\s*HIP\s+(\d+)", task.get("facts", ""))
            if hip:
                for obj in objects:
                    if any(re.search(r"\bHIP\s+" + hip.group(1) + r"\b", str(rec.get("source_key", "")), re.I) for rec in obj.get("source_records", [])):
                        existing.add(int(obj["fixed_object_id"]))
    selected = []
    for obj in sorted(objects, key=lambda o: (int(o["fixed_object_id"]) not in resumable, int(o["fixed_object_id"]))):
        ident = int(obj["fixed_object_id"])
        if ident in existing:
            continue
        if ident not in curated_ids:
            continue
        identity, query = registry_identity(active[ident])
        name = next(((r.get("facts") or {}).get("name") for r in obj.get("source_records", [])
                     if (r.get("facts") or {}).get("name")), query)
        selected.append({"id": str(ident), "fixed_object_id": ident,
                         "identity": identity, "title": str(name),
                         "facts": "Registry identity: " + query + ". Source catalog identity only; all other claims require verification.",
                         "sources": ["https://simbad.cds.unistra.fr/simbad/sim-id?Ident=" + quote(query)]})
        if len(selected) >= limit:
            break
    return selected

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", default="generated/luna-pilot-selected.json")
    parser.add_argument("--resume-interrupted", action="store_true",
                        help="Resume saved paid stages before selecting new objects")
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("limit must be 1..1000")
    selected = candidates(args.limit, resume_interrupted=args.resume_interrupted)
    scope, unresolved = curated_scope()
    report = {"identified_curated_objects": len(scope), "selected_count": len(selected),
              "unresolved_catalog_entries": unresolved}
    report_path = ROOT / "generated/story-selection-preflight.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print("UNRESOLVED CATALOG ENTRIES (excluded):", len(unresolved))
    if not selected:
        raise SystemExit("No new eligible objects found; no paid calls allowed")
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(selected, indent=2) + "\n")
    print("NEW CANDIDATES:", len(selected))
    for item in selected:
        print(item["id"], item["title"])
