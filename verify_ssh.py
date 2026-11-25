"""Verify a local registry bundle with independently pinned OpenSSH public keys."""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


NAMESPACE = "forgemesh-registry-v1"
REPOS = {"nexus": "nexus", "vie": "vie", "orbis": "anyps5"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path, limit):
    with path.open("rb") as source:
        data = source.read(limit + 1)
    require(len(data) <= limit, f"{path.name} exceeds the size limit")
    return data


def unique_object(pairs):
    obj = dict(pairs)
    require(len(obj) == len(pairs), "duplicate JSON key")
    return obj


def verify(bundle, pinned, swarm, minimum_version):
    signers = {}
    for line in read(pinned, 1024).decode("ascii").splitlines():
        match = re.fullmatch(r"(fm-[123]) ssh-ed25519 ([A-Za-z0-9+/]{68})(?: [!-~][ -~]*)?", line)
        require(match is not None, "invalid pinned signer entry")
        principal, key = match.groups()
        require(principal not in signers and key not in signers.values(), "pinned signers must be distinct")
        signers[principal] = key
    require(len(signers) == 3, "three independently pinned signers required")

    data = read(bundle / "registry.json", 256 * 1024)
    with tempfile.TemporaryDirectory() as work:
        trusted = Path(work) / "allowed_signers"
        trusted.write_text("".join(f"{name} ssh-ed25519 {key}\n" for name, key in signers.items()), encoding="ascii")
        signature = Path(work) / "signature"
        verified = 0
        for i in range(1, 4):
            try:
                signature.write_bytes(read(bundle / f"registry.json.{i}.sig", 4096))
            except FileNotFoundError:
                continue
            result = subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", trusted, "-I", f"fm-{i}", "-n", NAMESPACE, "-s", signature],
                input=data, capture_output=True, timeout=10,
            )
            verified += result.returncode == 0
        require(verified >= 2, "need valid signatures from two distinct pinned signers")

    registry = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    require(isinstance(registry, dict), "invalid registry object")
    version, expires = registry.get("version"), registry.get("expires")
    require(type(version) is int and version >= minimum_version >= 1, "registry version is below the trusted minimum")
    require(type(expires) is int and expires > time.time(), "registry has expired or has no valid expiry")
    entries = registry.get("swarms")
    require(isinstance(entries, list), "invalid swarm list")
    manifests = {}
    for entry in entries:
        require(isinstance(entry, dict), "invalid swarm manifest")
        name = entry.get("swarm")
        require(isinstance(name, str) and name in REPOS and name not in manifests, "unknown or duplicate swarm")
        require(entry.get("repository") == f"https://github.com/ForgeMesh-io/{REPOS[name]}", f"wrong repository for {name}")
        manifests[name] = entry
    require(swarm in manifests, "requested swarm is absent")
    manifest = manifests[swarm]
    require(type(manifest.get("protocol")) is int and manifest["protocol"] == 1, "unsupported protocol")
    require(manifest.get("status") in ("research", "alpha", "beta", "stable"), "swarm is not open for participation")
    ref = manifest.get("nexus_ref")
    require(isinstance(ref, str) and re.fullmatch(r"[a-f0-9]{40}", ref), "invalid NEXUS commit pin")
    path = manifest.get("instructions")
    require(isinstance(path, str) and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", path)
            and not {".", "..", ".git"}.intersection(path.split("/")), "invalid instructions path")
    images = manifest.get("images")
    require(isinstance(images, dict) and all(isinstance(image, str) and
            re.fullmatch(r"ghcr\.io/forgemesh-io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}", image)
            for image in images.values()), "images must be pinned to ForgeMesh digests")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("pinned_signers", type=Path)
    parser.add_argument("swarm", choices=REPOS)
    parser.add_argument("minimum_version", type=int)
    args = parser.parse_args()
    try:
        manifest = verify(args.bundle, args.pinned_signers, args.swarm, args.minimum_version)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"Registry verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
