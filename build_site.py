"""Build the static portal data from the swarm list, the TUF metadata and the swarms' state branches.

Usage: python build_site.py [--offline]
Writes site/data/portal.json. Numbers come only from real state files; when a
swarm has no state yet, its counters are null and the portal shows "no data".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
LEASED_OR_REVIEW = {"CLAIMED", "IN_PROGRESS", "CHANGES_REQUESTED", "SUBMITTED", "VALIDATING", "READY_TO_MERGE"}
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")


def fetch_state(repo_url: str) -> dict | None:
    owner_repo = repo_url.removeprefix("https://github.com/")
    url = f"https://raw.githubusercontent.com/{owner_repo}/forgemesh-state/state.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            state = json.loads(r.read())
            if isinstance(state, dict) and isinstance(state.get("tasks"), dict):
                return state
            return None
    except (urllib.error.URLError, ValueError):
        return None


def summarise(state: dict | None) -> dict | None:
    if not state:
        return None
    counts: dict[str, int] = {}
    tasks = []
    oldest = None
    for tid, t in sorted(state["tasks"].items()):
        s = t["display_status"]
        tasks.append({"id": tid, "status": s})
        counts[s] = counts.get(s, 0) + 1
        if s in ("SUBMITTED", "VALIDATING") and t.get("submission"):
            at = t["submission"].get("at")
            if at:
                oldest = min(oldest or at, at)
    claimants = {t["claimant"].lower() for t in state["tasks"].values() if t["status"] in LEASED_OR_REVIEW and t.get("claimant")}
    return {"as_of": state.get("clock"), "paused": state.get("paused", False), "counts": counts,
            "active_participants": len(claimants), "oldest_in_validation": oldest, "tasks": tasks}


def leaderboard(swarms):
    people = {}

    def credit(login, project, task, pr, kind):
        if not isinstance(login, str) or not LOGIN.fullmatch(login):
            return
        row = people.setdefault(login.lower(), {"login": login, "merged": 0, "validations": 0, "projects": {}})
        counts = row["projects"].setdefault(project, {"merged": 0, "validations": 0, "evidence": []})
        row[kind] += 1
        counts[kind] += 1
        counts["evidence"].append({"task": task, "pr": pr, "kind": kind})

    for project, state in swarms:
        if state is None:
            continue
        seen = set()
        for tid, task in sorted(state["tasks"].items()):
            sub = task.get("submission") or {}
            pr, sha, author = sub.get("pr"), sub.get("head_sha"), sub.get("author")
            if (task["status"] != "MERGED" or sub.get("audit") != [] or type(pr) is not int or pr <= 0
                    or pr in seen or not sha or not isinstance(author, str) or not LOGIN.fullmatch(author)):
                continue
            seen.add(pr)
            credit(author, project, tid, pr, "merged")
            validators = {author.lower()}
            for voter, vote in sorted(task.get("votes", {}).items()):
                if voter.lower() not in validators and vote.get("verdict") == "pass" and vote.get("sha") == sha:
                    validators.add(voter.lower())
                    credit(voter, project, tid, pr, "validations")
    return sorted(people.values(), key=lambda row: (-row["merged"], -row["validations"], row["login"].lower()))


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
    states = []
    for s in cfg["swarms"]:
        state = None if args.offline else fetch_state(s["repository"])
        states.append((s["swarm"], state))
        out["swarms"].append({**s, "stats": summarise(state)})
    out["leaderboard"] = leaderboard(states)
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "data" / "portal.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote site/data/portal.json ({len(out['swarms'])} swarms, anchor={'yes' if out['anchor'] else 'none'})")


if __name__ == "__main__":
    main()
