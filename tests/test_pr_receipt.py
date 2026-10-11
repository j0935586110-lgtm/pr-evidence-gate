"""Offline fail-closed receipt v1 tests; no shell, network or GitHub calls."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from pr_receipt import inspect
import pr_workflow


HEAD = "a" * 40
BASE = "b" * 40


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.joinpath("logs").mkdir()
        self.log = self.root / "logs" / "after.txt"
        self.log.write_text("4 passed in 2.0s\n")
        self.record = {
            "schema": "pr-evidence-gate/receipt/v1",
            "repository": "NousResearch/hermes-agent",
            "pr": 99053,
            "head_sha": HEAD,
            "baseline_sha": BASE,
            "checks": [
                {
                    "id": "linux-head-after", "phase": "after", "source_sha": HEAD,
                    "platform": "linux-x86_64", "outcome": "PASS", "exit_code": 0,
                    "artifact": self.artifact("logs/after.txt"),
                },
                {
                    "id": "hosted-ci", "phase": "hosted_ci", "source_sha": HEAD,
                    "platform": "github-hosted",
                    "outcome": "ACTION_REQUIRED", "exit_code": None,
                    "reason": "maintainer approval required",
                },
            ],
        }
        self.manifest = self.root / "receipt.json"
        self.write()

    def artifact(self, name):
        data = (self.root / name).read_bytes()
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data)}

    def write(self):
        self.manifest.write_text(json.dumps(self.record))

    def assert_blocked(self, reason=None):
        self.write()
        result = inspect(self.manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["safe_to_publish"])
        if reason:
            self.assertIn(reason, result["reasons"])
        return result

    def test_matching_hashes_are_not_trusted_or_release_authorization(self):
        result = inspect(self.manifest)
        self.assertEqual(result["status"], "HASHES_MATCH_UNTRUSTED")
        self.assertEqual(result["artifact_count"], 1)
        self.assertEqual(result["source_trust"], "self_reported_untrusted")
        self.assertTrue(result["current_head_after_test_reported"])
        self.assertTrue(result["hosted_ci_pending_or_unverified"])
        self.assertFalse(result["test_execution_verified"])
        self.assertFalse(result["review_authenticity_verified"])
        self.assertFalse(result["hosted_ci_verified"])
        self.assertFalse(result["safe_to_publish"])

    def test_tampered_log_is_blocked(self):
        self.log.write_text("999 passed\n")
        result = inspect(self.manifest)
        self.assertIn("artifact_hash_or_size_mismatch", result["reasons"])

    def test_same_size_modified_log_is_blocked(self):
        self.log.write_text("9 passed in 2.0s\n")
        self.assert_blocked("artifact_hash_or_size_mismatch")

    def test_missing_log_is_blocked(self):
        self.log.unlink()
        self.assert_blocked("unreadable_or_invalid_receipt")

    @unittest.skipIf(os.name == "nt", "symlink privileges not assured on Windows runners")
    def test_symlink_log_is_blocked(self):
        original = self.root / "actual.log"
        self.log.rename(original)
        self.log.symlink_to(original)
        self.assert_blocked("artifact_symlink_rejected")

    @unittest.skipIf(os.name == "nt", "symlink privileges not assured on Windows runners")
    def test_symlink_parent_is_blocked(self):
        target = self.root / "actual"
        (self.root / "logs").rename(target)
        (self.root / "logs").symlink_to(target, target_is_directory=True)
        self.assert_blocked("artifact_symlink_rejected")

    def test_escape_parent_path_is_blocked(self):
        self.record["checks"][0]["artifact"]["path"] = "../escape"
        self.assert_blocked("artifact_path_escape")

    def test_absolute_path_is_blocked(self):
        self.record["checks"][0]["artifact"]["path"] = str(self.log)
        self.assert_blocked("artifact_path_escape")

    def test_backslash_path_is_blocked(self):
        self.record["checks"][0]["artifact"]["path"] = r"..\escape"
        self.assert_blocked("artifact_path_invalid")

    def test_wrong_sha_is_blocked(self):
        self.record["checks"][0]["artifact"]["sha256"] = "f" * 64
        self.assert_blocked("artifact_hash_or_size_mismatch")

    def test_wrong_size_is_blocked(self):
        self.record["checks"][0]["artifact"]["bytes"] += 1
        self.assert_blocked("artifact_hash_or_size_mismatch")

    def test_check_missing_exit_code_is_blocked(self):
        self.record["checks"][0]["exit_code"] = None
        self.assert_blocked("exit_code_invalid")

    def test_fake_success_rc_is_blocked(self):
        self.record["checks"][0]["exit_code"] = 1
        self.assert_blocked("outcome_exit_code_mismatch")

    def test_expected_red_failure_can_be_recorded(self):
        self.record["checks"][0].update({
            "phase": "before", "source_sha": BASE,
            "outcome": "EXPECTED_FAILURE", "exit_code": 1,
        })
        self.write()
        result = inspect(self.manifest)
        self.assertEqual(result["status"], "HASHES_MATCH_UNTRUSTED")
        self.assertFalse(result["current_head_after_test_reported"])

    def test_reproduced_bug_passing_pytest_is_not_a_fix_claim(self):
        self.record["checks"][0].update({
            "phase": "mainline", "source_sha": BASE,
            "outcome": "REPRODUCED", "exit_code": 0,
        })
        self.write()
        result = inspect(self.manifest)
        self.assertEqual(result["status"], "HASHES_MATCH_UNTRUSTED")
        self.assertFalse(result["current_head_after_test_reported"])

    def test_action_required_cannot_pretend_success(self):
        self.record["checks"][1]["outcome"] = "PASS"
        self.record["checks"][1]["exit_code"] = 0
        self.assert_blocked("hosted_ci_not_trusted_from_local_log")

    def test_not_run_requires_reason(self):
        self.record["checks"][1]["outcome"] = "NOT_RUN"
        self.record["checks"][1]["reason"] = ""
        self.assert_blocked("unexecuted_check_missing_reason")

    def test_artifact_claim_on_unexecuted_check_blocked(self):
        self.record["checks"][1]["artifact"] = self.artifact("logs/after.txt")
        self.assert_blocked("unexecuted_check_claims_execution")

    def test_unexpected_schema_is_blocked(self):
        self.record["schema"] = "unknown/v9"
        self.assert_blocked("unsupported_receipt_schema")

    def test_duplicate_check_id_is_blocked(self):
        self.record["checks"][1]["id"] = "linux-head-after"
        self.assert_blocked("check_id_invalid_or_duplicate")

    def test_invalid_pr_bool_is_blocked(self):
        self.record["pr"] = True
        self.assert_blocked("pr_invalid")

    @unittest.skipIf(os.name == "nt", "symlink privileges not assured on Windows runners")
    def test_manifest_symlink_is_blocked(self):
        actual = self.root / "real.json"
        self.manifest.rename(actual)
        self.manifest.symlink_to(actual)
        result = inspect(self.manifest)
        self.assertEqual(result["status"], "BLOCKED")

    def test_manifest_over_one_meg_is_blocked(self):
        self.manifest.write_text(" " * (1024 * 1024 + 1))
        result = inspect(self.manifest)
        self.assertEqual(result["status"], "BLOCKED")

    def test_snapshot_match_required_when_worktree_given(self):
        with patch("pr_receipt.collect", return_value={
            "status": "BLOCKED", "local_head": HEAD
        }) as collect:
            result = inspect(self.manifest, worktree=str(self.root))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("remote_or_local_head_mismatch", result["reasons"])
        collect.assert_called_once()

    def test_snapshot_exact_sha_check(self):
        with patch("pr_receipt.collect", return_value={
            "status": "SNAPSHOT_MATCH_ONLY", "local_head": BASE
        }):
            result = inspect(self.manifest, worktree=str(self.root))
        self.assertEqual(result["status"], "BLOCKED")

    def test_good_snapshot_still_not_authorized(self):
        with patch("pr_receipt.collect", return_value={
            "status": "SNAPSHOT_MATCH_ONLY", "local_head": HEAD
        }):
            result = inspect(self.manifest, worktree=str(self.root))
        self.assertEqual(result["status"], "HASHES_MATCH_UNTRUSTED")
        self.assertFalse(result["safe_to_publish"])

    def test_shipped_synthetic_example_is_hash_consistent(self):
        sample = ROOT / "examples" / "receipt-v1" / "receipt.json"
        result = inspect(sample)
        self.assertEqual(result["status"], "HASHES_MATCH_UNTRUSTED")
        self.assertEqual(result["artifact_count"], 3)
        self.assertTrue(result["hosted_ci_pending_or_unverified"])
        self.assertFalse(result["safe_to_publish"])

    def test_workflow_receipt_cli_works_offline(self):
        with patch("sys.stdout"):
            rc = pr_workflow.main(["receipt", "--manifest", str(self.manifest)])
        self.assertEqual(rc, 0)

    def test_workflow_receipt_cli_blocked_on_tamper(self):
        self.log.write_text("TAMPER")
        with patch("sys.stdout"):
            rc = pr_workflow.main(["receipt", "--manifest", str(self.manifest)])
        self.assertEqual(rc, 2)

    def test_receipt_no_shell_or_untrusted_test_execution(self):
        with patch("subprocess.run", side_effect=AssertionError("must not execute")):
            result = inspect(self.manifest)
        self.assertEqual(result["status"], "HASHES_MATCH_UNTRUSTED")


if __name__ == "__main__":
    unittest.main()
