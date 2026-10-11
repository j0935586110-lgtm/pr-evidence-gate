#!/usr/bin/env python3
"""Offline red-team cases for Hermes artifact audit; never calls GitHub/models."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "tools" / "verify_hermes_run.py"
import sys
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("verify_hermes_run", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
HEAD = "a" * 40
REPO = "NousResearch/hermes-agent"
PR = 99053


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # macOS /var -> /private/var and Windows path normalization otherwise
        # make a logically identical worktree fail its exact-root comparison.
        self.path = Path(self.tmp.name).resolve()
        self.hd = self.path / ".hermes"
        (self.hd / "logs").mkdir(parents=True)
        (self.hd / "logs/red.log").write_text("expected failing regression\n")
        (self.hd / "logs/verify.log").write_text("all tests pass\n")
        self.status = {
            "repo": REPO, "worktree": str(self.path),
            "state": "READY_FOR_PUSH", "head": {"sha": HEAD},
            "red": {"ok": True, "evidence": "logs/red.log", "rc": 1},
            "verify": {"ok": True, "evidence": "logs/verify.log", "rc": 0},
            "review": {"ok": True, "reviewed_sha": HEAD, "verdict": "approve",
                       "github_read": True, "blockers": []},
        }
        self.acceptance = {
            "repo": REPO, "gates": {
                k: {"ok": True} for k in
                ("red_evidence", "tests_pass", "head_match", "review_approved")
            },
        }
        self.base = {
            "status": "SNAPSHOT_MATCH_ONLY", "reasons": [], "local_head": HEAD,
            "not_verified": ["CI"], "public_actions_authorized": False,
        }

    def run_audit(self):
        (self.hd / "status.json").write_text(json.dumps(self.status))
        (self.hd / "acceptance.json").write_text(json.dumps(self.acceptance))
        with patch.object(mod, "collect", return_value=self.base):
            return mod.audit(REPO, PR, str(self.path))

    def test_matching_records_still_untrusted(self):
        x = self.run_audit()
        self.assertEqual(x["status"], "RECORDED_GATES_MATCH_UNTRUSTED")
        self.assertFalse(x["public_actions_authorized"])
        self.assertFalse(x["hermes_gates"]["independent_test_execution_verified"])

    def test_dirty_git_blocks(self):
        self.base["reasons"] = ["dirty_worktree"]
        self.assertIn("dirty_worktree", self.run_audit()["reasons"])

    def test_old_github_head_blocks(self):
        self.base["reasons"] = ["head_mismatch"]
        self.assertEqual(self.run_audit()["status"], "BLOCKED")

    def test_nonready_state_blocks(self):
        self.status["state"] = "VERIFY"
        self.assertIn("hermes_run_not_ready", self.run_audit()["reasons"])

    def test_test_gate_false_blocks(self):
        self.status["verify"]["ok"] = False
        self.assertIn("hermes_verify_not_passed", self.run_audit()["reasons"])

    def test_test_exit_nonzero_blocks(self):
        self.status["verify"]["rc"] = 23
        self.assertIn("hermes_verify_exit_not_zero", self.run_audit()["reasons"])

    def test_reviewed_head_wrong_blocks(self):
        self.status["review"]["reviewed_sha"] = "b" * 40
        self.assertIn("hermes_reviewed_head_mismatch", self.run_audit()["reasons"])

    def test_recorded_head_wrong_blocks(self):
        self.status["head"]["sha"] = "b" * 40
        self.assertIn("hermes_recorded_head_mismatch", self.run_audit()["reasons"])

    def test_fake_github_read_blocks(self):
        self.status["review"]["github_read"] = False
        self.assertIn("hermes_review_not_approved", self.run_audit()["reasons"])

    def test_review_blocker_blocks(self):
        self.status["review"]["blockers"] = ["security"]
        self.assertIn("hermes_review_not_approved", self.run_audit()["reasons"])

    def test_acceptance_gate_false_blocks(self):
        self.acceptance["gates"]["tests_pass"]["ok"] = False
        self.assertIn("acceptance_tests_pass_not_passed", self.run_audit()["reasons"])

    def test_missing_log_blocks(self):
        (self.hd / "logs/verify.log").unlink()
        self.assertIn("missing_verify_log", self.run_audit()["reasons"])

    def test_empty_log_blocks(self):
        (self.hd / "logs/verify.log").write_text("")
        self.assertIn("missing_verify_log", self.run_audit()["reasons"])

    def test_directory_escape_blocks(self):
        self.status["verify"]["evidence"] = "../outside.log"
        self.assertIn("verify_log_path_escape", self.run_audit()["reasons"])

    def test_symlink_escape_blocks(self):
        external = self.path / "outside.log"
        external.write_text("not trusted")
        (self.hd / "logs/verify.log").unlink()
        (self.hd / "logs/verify.log").symlink_to(external)
        self.assertIn("verify_log_path_escape", self.run_audit()["reasons"])

    def test_status_repo_mismatch_blocks(self):
        self.status["repo"] = "another/repo"
        self.assertIn("hermes_repo_mismatch", self.run_audit()["reasons"])

    def test_malformed_head_refuses_cleanly(self):
        self.status["head"] = "malformed"
        self.assertIn("hermes_recorded_head_mismatch", self.run_audit()["reasons"])

    def test_malformed_review_refuses_cleanly(self):
        self.status["review"] = ["unexpected list"]
        self.assertIn("hermes_review_not_passed", self.run_audit()["reasons"])

    def test_symlinked_hermes_directory_refused(self):
        target = self.path / "other"
        target.mkdir()
        (self.hd / "logs/verify.log").unlink()
        for entry in self.hd.rglob("*"):
            pass
        import shutil
        shutil.rmtree(self.hd)
        self.hd.symlink_to(target, target_is_directory=True)
        with patch.object(mod, "collect", return_value=self.base):
            result = mod.audit(REPO, PR, str(self.path))
        self.assertIn("hermes_directory_unsafe", result["reasons"])

    def test_oversized_status_refused(self):
        (self.hd / "status.json").write_bytes(b" " * (1_048_576 + 1))
        (self.hd / "acceptance.json").write_text(json.dumps(self.acceptance))
        with patch.object(mod, "collect", return_value=self.base):
            result = mod.audit(REPO, PR, str(self.path))
        self.assertIn("missing_or_invalid_hermes_artifacts", result["reasons"])

    def test_status_file_symlink_rejected(self):
        outside=self.path / "status-outside.json"
        outside.write_text(json.dumps(self.status))
        link=self.hd/"status.json"
        link.symlink_to(outside)
        (self.hd/"acceptance.json").write_text(json.dumps(self.acceptance))
        with patch.object(mod, "collect", return_value=self.base):
            res=mod.audit(REPO,PR,str(self.path))
        self.assertIn("missing_or_invalid_hermes_artifacts",res["reasons"])

    def test_nonobject_acceptance_gate_blocks(self):
        self.acceptance["gates"]["tests_pass"] = True
        self.assertIn("acceptance_tests_pass_not_passed",self.run_audit()["reasons"])

    def test_bounded_reader_accepts_normal_json(self):
        p=self.hd/"small.json"
        p.write_text('{"ok": true}')
        self.assertEqual(mod.read_json(p),{"ok":True})

    def test_reader_rejects_nonregular_directory(self):
        with self.assertRaises((ValueError, OSError)):
            mod.read_json(self.hd/"logs")

    def test_no_artifacts_blocks(self):
        with patch.object(mod, "collect", return_value=self.base):
            res = mod.audit(REPO, PR, str(self.path))
        self.assertIn("missing_or_invalid_hermes_artifacts", res["reasons"])

    def test_status_is_not_a_permission_to_publish(self):
        x = self.run_audit()
        self.assertIn("trusted_review", x["not_verified"])
        self.assertNotIn("APPROVED", x["status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
