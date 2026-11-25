"""Create or update the DEVELOPMENT registry under site/ (metadata + targets).

Keys are stored in ~/.forgemesh-dev-keys (outside every repository). They are
throw-away development keys: the resulting root is marked "development" and the
portal shows a warning. Production uses the ceremony in nexus/docs/KEY_CEREMONY.md.

Usage:
    python dev_registry.py init                 # new root (new anchor!)
    python dev_registry.py publish <swarm> <manifest.json>
    python dev_registry.py refresh              # re-sign snapshot/timestamp
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get("FORGEMESH_NEXUS", str(HERE.parent / "nexus")))

from forgemesh import config, registry as reg  # noqa: E402

KEYS = Path(os.environ.get("FORGEMESH_KEYS", Path.home() / ".forgemesh-dev-keys"))
SITE = HERE / "site"
SWARMS = [s["swarm"] for s in json.loads((HERE / "swarms.json").read_text())["swarms"]]


def main(argv: list[str]) -> None:
    repo, kr = reg.Repo(SITE), reg.Keyring(KEYS)
    if argv[:1] == ["init"]:
        print("trust anchor:", reg.init_dev(SITE, KEYS, SWARMS))
    elif argv[:1] == ["publish"] and len(argv) == 3:
        swarm, manifest = argv[1], json.loads(Path(argv[2]).read_text())
        config.validate(manifest, "manifest")
        assert manifest["swarm"] == swarm
        repo.add_target(swarm, "manifest.json", reg.dumps_manifest(manifest), [kr.get(f"DEV-swarm-{swarm}")])
        repo.refresh(kr.get("DEV-snapshot"), kr.get("DEV-timestamp"))
        print(f"published swarms/{swarm}/manifest.json")
    elif argv[:1] == ["refresh"]:
        repo.refresh(kr.get("DEV-snapshot"), kr.get("DEV-timestamp"))
        print("snapshot/timestamp refreshed")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
