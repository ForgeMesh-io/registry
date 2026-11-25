import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RegistryVerification(unittest.TestCase):
    def test_threshold_replay_and_destination(self):
        script = Path(__file__).resolve().with_name("verify_ssh.py")
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            keys = []
            for i in range(1, 4):
                key = root / f"key{i}"
                subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", key], check=True)
                keys.append(key)
            (root / "allowed_signers").write_text("".join(
                f"fm-{i} " + Path(f"{key}.pub").read_text() for i, key in enumerate(keys, 1)))
            manifest = {"swarm": "nexus", "repository": "https://github.com/ForgeMesh-io/nexus", "status": "alpha",
                        "instructions": "AGENTS.md", "nexus_ref": "a" * 40, "images": {}, "protocol": 1}
            bundle = {"version": 2, "expires": 4102444800, "swarms": [manifest]}
            path = root / "registry.json"

            def sign(signers=(1, 2)):
                path.write_text(json.dumps(bundle))
                for i in (1, 2, 3):
                    sig = root / f"registry.json.{i}.sig"
                    sig.unlink(missing_ok=True)
                    if i not in signers:
                        continue
                    with path.open("rb") as source, sig.open("wb") as target:
                        subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", keys[i - 1], "-n", "forgemesh-registry-v1"], stdin=source, stdout=target, check=True)

            def verify(minimum=1, swarm="nexus"):
                result = subprocess.run([sys.executable, script, root, root / "allowed_signers", swarm, str(minimum)], capture_output=True, text=True)
                if result.returncode:
                    self.assertEqual(result.stdout, "")
                return result

            sign()
            valid = verify()
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertEqual(json.loads(valid.stdout), manifest)
            sign((2, 3))
            self.assertEqual(verify().returncode, 0)
            self.assertNotEqual(verify(swarm="vie").returncode, 0)
            self.assertNotEqual(verify(3).returncode, 0)
            path.write_text(path.read_text() + "\n")
            self.assertNotEqual(verify().returncode, 0)
            sign()
            (root / "registry.json.2.sig").write_bytes((root / "registry.json.1.sig").read_bytes())
            self.assertNotEqual(verify().returncode, 0)
            allowed = root / "allowed_signers"
            original = allowed.read_text()
            duplicate = original.splitlines(keepends=True)
            duplicate[1] = duplicate[0].replace("fm-1 ", "fm-2 ", 1)
            allowed.write_text("".join(duplicate))
            self.assertNotEqual(verify().returncode, 0)
            allowed.write_text(original)
            bundle["expires"] = 1
            sign()
            self.assertNotEqual(verify().returncode, 0)
            bundle["expires"] = 4102444800
            manifest["repository"] = "https://github.com/other/nexus"
            sign()
            self.assertNotEqual(verify().returncode, 0)
            manifest["repository"] = "https://github.com/ForgeMesh-io/nexus"
            manifest["images"] = {"build": "ghcr.io/forgemesh-io/nexus:latest"}
            sign()
            self.assertNotEqual(verify().returncode, 0)
