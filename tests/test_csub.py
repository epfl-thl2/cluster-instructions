"""Offline CLI integration checks. No test can invoke a real kubectl."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "csub.py"


class NoDuplicateLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        pairs = self.construct_pairs(node, deep=deep)
        mapping = dict(pairs)
        if len(mapping) != len(pairs):
            raise AssertionError("duplicate manifest key")
        return mapping


class SubmissionCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "user.yaml"
        self.record = self.root / "kubectl-calls.jsonl"
        self.config = {
            "user": "alice", "uid": 123456, "group": "THL2-unit", "gid": 11167,
            "supplemental_groups": [84730], "working_dir": "/thl2/alice", "context": "lab-rcp",
        }
        self.write_config()
        fake = self.root / "kubectl"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "entry = {'argv': sys.argv[1:], 'stdin': sys.stdin.read()}\n"
            "with Path(os.environ['CSUB_RECORD']).open('a') as f:\n"
            "    f.write(json.dumps(entry) + '\\n')\n"
            "code = int(os.environ.get('CSUB_EXIT', '0'))\n"
            "if code:\n"
            "    print('AlreadyExists fake-wandb-token fake-hf-token', file=sys.stderr)\n"
            "else:\n"
            "    print('workload created')\n"
            "sys.exit(code)\n"
        )
        fake.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ.get("PATH", ""), CSUB_RECORD=str(self.record))
        for key in ("WANDB_API_KEY", "HF_TOKEN", "CSUB_EXIT"):
            self.env.pop(key, None)

    def write_config(self):
        self.config_path.write_text(yaml.safe_dump(self.config))

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--user", str(self.config_path), *args],
                              cwd=self.root, env=self.env, capture_output=True, text=True, check=False)

    def preview(self, *args):
        result = self.run_cli("--dry", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.record.exists(), "preview unexpectedly contacted kubectl")
        return yaml.load(result.stdout, Loader=NoDuplicateLoader)

    def calls(self):
        return [json.loads(line) for line in self.record.read_text().splitlines()]

    def test_preview_defaults_and_persistent_identity(self):
        doc = self.preview("--name", "dev")
        self.assertEqual(doc["kind"], "InteractiveWorkload")
        self.assertEqual(doc["metadata"]["namespace"], "runai-thl2-alice")
        spec = doc["spec"]
        self.assertEqual(spec["arguments"]["value"], "sleep 3600")
        self.assertEqual(spec["runAsUid"]["value"], 123456)
        self.assertEqual(spec["supplementalGroups"]["value"], "84730")
        env = spec["environment"]["items"]
        self.assertEqual(env["HOME"]["value"], "/alice")
        self.assertNotIn("HF_TOKEN", env)
        mounts = [entry["value"] for entry in spec["pvcs"]["items"].values()]
        self.assertEqual({(m["claimName"], m["path"]) for m in mounts}, {("home", "/alice"), ("thl2-scratch", "/thl2")})

    def test_quotes_newlines_and_unicode_round_trip(self):
        command = 'bash -c \'printf "%s\\n" "hello: λ # test"\'\necho "second line"'
        doc = self.preview("--train", "--command", command)
        self.assertEqual(doc["spec"]["arguments"]["value"], command)

    def test_idle_duration_is_parsed_fully(self):
        doc = self.preview("--time", "1d2h30m4s", "--gpus", "0")
        self.assertEqual(doc["spec"]["arguments"]["value"], "sleep 95404")
        self.assertEqual(doc["spec"]["gpu"]["value"], "0")

    def test_large_shm_switches_emit_unambiguous_yaml(self):
        self.assertTrue(self.preview("--large_shm")["spec"]["largeShm"]["value"])
        self.assertFalse(self.preview("--no-large-shm")["spec"]["largeShm"]["value"])

    def test_training_retry_and_pool_fields(self):
        doc = self.preview("--train", "--command", "/bin/true", "--node-type", "h100", "--backoff-limit", "2", "--host-ipc")
        self.assertEqual(doc["kind"], "TrainingWorkload")
        self.assertEqual(doc["spec"]["backoffLimit"]["value"], 2)
        self.assertTrue(doc["spec"]["hostIpc"]["value"])
        self.assertNotIn("preemptible", doc["spec"])
        interactive = self.preview("--node_type", "h100")
        self.assertTrue(interactive["spec"]["preemptible"]["value"])

    def test_redacted_preview_and_optional_legacy_tokens(self):
        self.config.update(wandb_api_key="fake-wandb-token", hf_token="fake-hf-token")
        self.write_config()
        result = self.run_cli("--dry")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("fake-wandb-token", result.stdout + result.stderr)
        self.assertNotIn("fake-hf-token", result.stdout + result.stderr)
        doc = yaml.safe_load(result.stdout)
        self.assertEqual(doc["spec"]["environment"]["items"]["HF_TOKEN"]["value"], "REDACTED")
        self.assertFalse(self.record.exists())

    def test_submit_uses_exact_target_once_and_preserves_command(self):
        self.env.update(WANDB_API_KEY="fake-wandb-token", HF_TOKEN="fake-hf-token")
        command = 'bash /thl2/alice/run.sh --label "a:b"; echo "$HOME"'
        result = self.run_cli("--name", "trial", "--context", "override-rcp", "--train", "--command", command)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["argv"], ["--context", "override-rcp", "--namespace", "runai-thl2-alice", "create", "-f", "-"])
        doc = yaml.load(calls[0]["stdin"], Loader=NoDuplicateLoader)
        self.assertEqual(doc["spec"]["arguments"]["value"], command)
        self.assertEqual(doc["spec"]["environment"]["items"]["HF_TOKEN"]["value"], "fake-hf-token")
        self.assertIn("running state has not been checked", result.stdout)
        self.assertNotIn("fake-hf-token", result.stdout + result.stderr)

    def test_existing_name_or_server_error_is_not_retried(self):
        self.env.update(CSUB_EXIT="1", WANDB_API_KEY="fake-wandb-token", HF_TOKEN="fake-hf-token")
        result = self.run_cli("--name", "existing")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.calls()), 1)
        self.assertIn("AlreadyExists", result.stderr)
        self.assertIn("never updated", result.stderr)
        self.assertNotIn("fake-wandb-token", result.stdout + result.stderr)
        self.assertNotIn("fake-hf-token", result.stdout + result.stderr)

    def test_environment_overrides_yaml_including_empty(self):
        self.config.update(wandb_api_key="legacy-token", hf_token="legacy-hf-token")
        self.write_config()
        self.env.update(WANDB_API_KEY="environment-token", HF_TOKEN="")
        result = self.run_cli("--name", "tokens")
        self.assertEqual(result.returncode, 0, result.stderr)
        env = yaml.safe_load(self.calls()[0]["stdin"])["spec"]["environment"]["items"]
        self.assertEqual(env["WANDB_API_KEY"]["value"], "environment-token")
        self.assertNotIn("HF_TOKEN", env)

    def test_bad_options_fail_before_kubectl(self):
        cases = [
            ("--train",), ("--command", ""), ("--command", "true", "--time", "1h"),
            ("--time", "1hgarbage"), ("--time", "0s"), ("--time", ""), ("--time", "-1h"),
            ("--gpus", "-1"), ("--cpus", "0"), ("--memory", "0Gi"), ("--memory", "32bogus"),
            ("--name", "Bad_Name"), ("--name", ""), ("--name", "x" * 64),
            ("--context", ""), ("--backofflimit", "1"), ("--backofflimit", "-1"),
        ]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.record.exists())

    def test_missing_required_config_is_actionable(self):
        del self.config["supplemental_groups"]
        self.write_config()
        result = self.run_cli("--dry")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("supplemental_groups", result.stderr)
        self.assertFalse(self.record.exists())

    def test_invalid_config_ids_and_paths_fail_locally(self):
        for key, value in (("uid", True), ("gid", -1), ("supplemental_groups", []),
                           ("working_dir", "/tmp/code"), ("working_dir", "/thl2/../tmp")):
            with self.subTest(key=key, value=value):
                original = self.config[key]
                self.config[key] = value
                self.write_config()
                self.assertNotEqual(self.run_cli("--dry").returncode, 0)
                self.assertFalse(self.record.exists())
                self.config[key] = original

    def test_duplicate_yaml_keys_are_rejected(self):
        self.config_path.write_text(self.config_path.read_text() + "uid: 999999\n")
        result = self.run_cli("--dry")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate keys", result.stderr)

    def test_invalid_yaml_never_echoes_secret_source_line(self):
        self.config_path.write_text('hf_token: ["fake-hf-token"\n')
        result = self.run_cli("--dry")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("fake-hf-token", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_legacy_group_and_symlinks_config_migrates(self):
        self.config.update(supplemental_groups="84730, 11167", symlinks={".ssh": ["dir", ".ssh"]})
        self.write_config()
        result = self.run_cli("--dry")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ignored", result.stderr)
        self.assertEqual(yaml.safe_load(result.stdout)["spec"]["supplementalGroups"]["value"], "84730,11167")


if __name__ == "__main__":
    unittest.main()
