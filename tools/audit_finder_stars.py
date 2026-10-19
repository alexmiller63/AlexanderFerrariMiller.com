#!/usr/bin/env python3
"""Read-only audit of 2026 planetary finder reference stars and canonical stories."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(year: int, output: Path):
    folder = ROOT / "generated-sky-notes" / str(year)
    rows = {}
    issues = []
    files = []
    for week in range(1, 54):
        name = f"W{week:02d}"
        path = folder / f"{name}.json"
        if not path.is_file():
            issues.append({"week": name, "issue": "missing_week_json", "detail": str(path.relative_to(ROOT))})
            continue
        files.append(name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            issues.append({"week": name, "issue": "unreadable_json", "detail": str(exc)})
            continue
        relations = data.get("planet_finder_relations", [])
        artworks = data.get("planet_finder_artworks", [])
        for rel in relations:
            star = rel.get("star")
            if not star:
                continue
            sid = rel.get("star_fixed_object_id")
            if sid in (None, ""):
                issues.append({"week": name, "issue": "missing_fixed_object_id", "detail": f"{rel.get('planet')}: {star}"})
                key = f"NAME:{star}"
            else:
                key = str(sid)
            item = rows.setdefault(key, {"fixed_object_id": sid, "name": star, "weeks": set(), "planets": set(), "names": set(), "chart_weeks": set()})
            item["weeks"].add(name)
            item["planets"].add(str(rel.get("planet", "")))
            item["names"].add(star)
            for art in artworks:
                if any(t.get("type") == "reference-star" and (str(t.get("fixed_object_id")) == str(sid) if sid is not None else t.get("name") == star) for t in art.get("targets", [])):
                    item["chart_weeks"].add(name)
        # Also include finder-chart reference stars not represented in the relation list.
        for art in artworks:
            for target in art.get("targets", []):
                if target.get("type") != "reference-star":
                    continue
                star, sid = target.get("name"), target.get("fixed_object_id")
                if not star:
                    continue
                key = str(sid) if sid not in (None, "") else f"NAME:{star}"
                item = rows.setdefault(key, {"fixed_object_id": sid, "name": star, "weeks": set(), "planets": set(), "names": set(), "chart_weeks": set()})
                item["weeks"].add(name)
                item["chart_weeks"].add(name)
                item["names"].add(star)
                for t in art.get("targets", []):
                    if t.get("type") == "solar-system-object":
                        item["planets"].add(str(t.get("name", "")))
                if sid in (None, ""):
                    issues.append({"week": name, "issue": "chart_reference_missing_id", "detail": star})
    output.mkdir(parents=True, exist_ok=True)
    inventory = []
    for key, item in sorted(rows.items(), key=lambda p: (p[1]["name"].casefold(), p[0])):
        sid = item["fixed_object_id"]
        story_file = ROOT / "stories" / "baseline" / f"{sid}.html" if sid is not None else None
        curated = []
        if sid is not None:
            curated = [str(p.relative_to(ROOT)) for p in (ROOT / "stories").glob(f"*/{sid}.md")]
        exists = bool(story_file and story_file.is_file())
        story_text = story_file.read_text(encoding="utf-8") if exists else ""
        hed = 'data-story-field="hed"' in story_text
        dek = 'data-story-field="dek"' in story_text
        body = 'data-story-field="body"' in story_text
        if len(item["names"]) > 1:
            issues.append({"week": ",".join(sorted(item["weeks"])), "issue": "multiple_names_same_id", "detail": f"{sid}: {sorted(item['names'])}"})
        if not exists:
            issues.append({"week": ",".join(sorted(item["weeks"])), "issue": "missing_baseline_story", "detail": f"{sid}: {item['name']}"})
        elif not all((hed, dek, body)):
            issues.append({"week": ",".join(sorted(item["weeks"])), "issue": "incomplete_baseline_story", "detail": f"{sid}: {item['name']}"})
        inventory.append({
            "fixed_object_id": sid, "name": item["name"], "weeks_count": len(item["weeks"]),
            "weeks": ",".join(sorted(item["weeks"])), "planets": ",".join(sorted(item["planets"])),
            "finder_chart_weeks": len(item["chart_weeks"]),
            "baseline_story": exists, "hed": hed, "dek": dek, "body": body,
            "curated_story_paths": ",".join(sorted(curated)),
            "story_url": f"/stories/baseline/{sid}.html" if exists else "",
        })
    with (output / "finder-stars.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(inventory[0]) if inventory else ["fixed_object_id", "name"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(inventory)
    (output / "issues.json").write_text(json.dumps(issues, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    missing = sum(not x["baseline_story"] for x in inventory)
    summary = [
        f"# {year} Finder-Star Audit", "",
        f"- Weekly JSON files found: {len(files)}/53",
        f"- Unique finder-star identities: {len(inventory)}",
        f"- Finder stars with baseline stories: {len(inventory) - missing}",
        f"- Finder stars missing baseline stories: {missing}",
        f"- Issues detected: {len(issues)}", "",
        "Sources: generated-sky-notes weekly planet_finder_relations and planet_finder_artworks; stories/baseline and curated Markdown.",
        "The audit is read-only; it does not regenerate charts or stories.",
        "A story file existing does not establish that every Planet Finder HTML page links to it.", "",
        "## Issues", ""
    ]
    summary += [f"- {i['week']}: {i['issue']} — {i['detail']}" for i in issues] or ["None."]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary[:8]))
    return 0 if len(files) == 53 else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--output", type=Path, default=Path("audit-output/finder-stars"))
    args = parser.parse_args()
    raise SystemExit(run(args.year, args.output))
