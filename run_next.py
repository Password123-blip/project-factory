#!/usr/bin/env python3
"""Pick the next unused idea, write its spec, print the slug. Deterministic."""
import json, sys
from pathlib import Path

base = Path(__file__).parent
registry = json.loads((base / "registry.json").read_text())
ideas = json.loads((base / "ideas.json").read_text())["backlog"]

used = {p["slug"] for p in registry["created"]}

next_idea = None
for idea in ideas:
    if idea["slug"] in used:
        continue
    if (base / "specs" / f"{idea['slug']}.json").exists():
        continue
    next_idea = idea
    break

if not next_idea:
    print("EXHAUSTED: no unused ideas left. Add more to ideas.json.", file=sys.stderr)
    sys.exit(2)

spec = {
    "slug": next_idea["slug"],
    "title": next_idea["title"],
    "tagline": next_idea["tagline"],
    "description": next_idea["tagline"] + ".",
    "category": next_idea["category"],
    "accent": "#4f46e5",
    "accent_soft": "#eef2ff",
    "table": next_idea["table"],
    "features": next_idea["features"],
    "seed": [],
}
(base / "specs").mkdir(exist_ok=True)
path = base / "specs" / f"{next_idea['slug']}.json"
path.write_text(json.dumps(spec, indent=2))
print(next_idea["slug"])
