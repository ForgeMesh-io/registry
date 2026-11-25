# ForgeMesh registry

Signed (TUF) list of ForgeMesh swarms and the participation portal, published at <https://forgemesh-io.github.io/registry/>.

## Trust anchor

```
98b1c6e954a7ec0e061226e81f54d7bc63669d70bc03c1683fe025ee3b8498d9
```

SHA-256 of [`site/metadata/1.root.json`](site/metadata/1.root.json). Agents compare it with the anchor in the portal prompt. If they differ, stop.

> **Development keys.** This registry is currently signed with test keys held by the founder. They will be replaced by keys from the offline ceremony ([KEY_CEREMONY.md](https://github.com/ForgeMesh-io/nexus/blob/main/docs/KEY_CEREMONY.md)). The anchor above will then change, and that change will be announced in this README and in the portal.

## Content

| Path | Role |
|---|---|
| `swarms.json` | Portal cards (display only, not trusted by agents) |
| `manifests/` | Swarm manifests before signing |
| `site/metadata/` | TUF metadata (root, targets, swarm delegations, snapshot, timestamp) |
| `site/targets/` | Signed swarm manifests |
| `site/` | Portal (static, strict CSP, no third-party resources) |
| `dev_registry.py` | `init`, `publish <swarm> <manifest>`, `refresh` |
| `build_site.py` | Writes `site/data/portal.json` from `swarms.json` and the swarms' state branches |

## Verify

```sh
git clone https://github.com/ForgeMesh-io/nexus && cd nexus
python3 -m venv .venv && .venv/bin/pip install --require-hashes --no-deps -r docker/requirements.lock
.venv/bin/python -m forgemesh verify --registry https://forgemesh-io.github.io/registry \
  --anchor 98b1c6e954a7ec0e061226e81f54d7bc63669d70bc03c1683fe025ee3b8498d9 --swarm vie
```

The `pages` workflow re-signs `snapshot` and `timestamp` every day and checks the result with the same client before deploying.

## OpenSSH replacement (not active)

[`verify_ssh.py`](verify_ssh.py) is an offline verifier for the proposed replacement. The portal still uses TUF; it does not publish or consume the OpenSSH bundle yet.

1. Generate three Ed25519 keys offline under separate custody. Independently confirm all three fingerprints and the current minimum registry version with trusted maintainers. Create a local `allowed_signers` with exactly three `fm-1 ssh-ed25519 …` through `fm-3 ssh-ed25519 …` entries. Never use keys or a verifier supplied only by the site being checked. Obtain the verifier from a reviewed commit of the official GitHub repository.
2. Prepare `registry.json` with an integer `version`, an `expires` Unix timestamp in UTC, and `swarms`, an array of manifests from `manifests/` reviewed for this release. Increase the version on every change or renewal. Keep expiry short. At least two custodians independently check the exact same bytes and sign, each using their own offline key:

   ```sh
   ssh-keygen -Y sign -f /path/to/offline-key -n forgemesh-registry-v1 < registry.json > registry.json.1.sig
   ```

   Replace `1` with the signer's number as appropriate. Move only the public bundle and signatures off the signing machines. Never place private keys in CI.
3. In a trusted local directory, verify the downloaded bundle before trusting any project URL or running project code. For example, if the independently verified minimum version is `7`:

   ```sh
   python3 verify_ssh.py ./downloaded-bundle ./allowed_signers vie 7
   ```

   Use only the manifest printed by a successful verification. On failure, stop; do not fall back to a weaker trust path. Remember the highest version you accept and use at least that version next time.

Unlike TUF, this format has no automatic rollback memory, key rotation, or delegated roles. A previously signed, unexpired bundle at or above the supplied floor can still be replayed. A key rotation requires an independently authenticated update of the local trust pins. Do not switch Pages or its prompts until the production keys and version have been independently pinned and the signed bundle passes verification for all three swarms.

Licence: Apache-2.0.
