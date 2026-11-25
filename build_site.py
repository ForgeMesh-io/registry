"""Build the static portal data from the swarm list, the TUF metadata and the swarms' state branches.

Usage: python build_site.py [--offline]
Writes site/data/portal.json. Numbers come only from real state files; when a
swarm has no state yet, its counters are null and the portal shows "no data".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"


def fetch_state(repo_url: str) -> dict | None:
    owner_repo = repo_url.removeprefix("https://github.com/")
    url = f"https://raw.githubusercontent.com/{owner_repo}/forgemesh-state/state.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, ValueError):
        return None


def summarise(state: dict | None) -> dict | None:
    if not state:
        return None
    counts: dict[str, int] = {}
    oldest = None
    for t in state["tasks"].values():
        s = t["display_status"]
        counts[s] = counts.get(s, 0) + 1
        if s in ("SUBMITTED", "VALIDATING") and t.get("submission"):
            at = t["submission"].get("at")
            oldest = min(oldest or at, at)
    claimants = {t["claimant"] for t in state["tasks"].values() if t.get("claimant")}
    return {"as_of": state.get("clock"), "paused": state.get("paused", False), "counts": counts,
            "active_participants": len(claimants), "oldest_in_validation": oldest}


def anchor() -> dict | None:
    root = SITE / "metadata" / "1.root.json"
    if not root.exists():
        return None
    data = json.loads(root.read_bytes())
    env = data["signed"].get("x-forgemesh", {}).get("environment", "production")
    return {"sha256": hashlib.sha256(root.read_bytes()).hexdigest(), "environment": env}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="do not fetch state branches")
    args = ap.parse_args()
    cfg = json.loads((HERE / "swarms.json").read_text())
    out = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "registry_url": cfg["registry_url"],
           "protocol": cfg["protocol"], "anchor": anchor(), "swarms": []}
    for s in cfg["swarms"]:
        out["swarms"].append({**s, "stats": None if args.offline else summarise(fetch_state(s["repository"]))})
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "data" / "portal.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote site/data/portal.json ({len(out['swarms'])} swarms, anchor={'yes' if out['anchor'] else 'none'})")


if __name__ == "__main__":
    main()
