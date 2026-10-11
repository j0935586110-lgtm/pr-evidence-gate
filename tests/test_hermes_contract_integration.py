#!/usr/bin/env python3
"""Contract test against the existing Hermes Loop implementation, with fake PR head.

No agent, model, external GitHub or real worktree is called.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("HERMES_LOOP_SCRIPT", str(Path.home()/".hermes/scripts/hermes_loop.py")))
sys.path.insert(0, str(ROOT / "tools"))
import verify_hermes_run


def import_hermes():
    spec = importlib.util.spec_from_file_location("existing_hermes_loop", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(SCRIPT.exists(), "Hermes Loop not on this host")
class ExistingHermesContract(unittest.TestCase):
    def setUp(self):
        self.hermes = import_hermes()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.h = self.root / ".hermes"
        (self.h/"logs").mkdir(parents=True)
        for f in ["red-fixture.log", "verify-fixture.log"]:
            (self.h/"logs"/f).write_text("fixture nonempty\n")
        self.sha = "a" * 40
        self.repo = "NousResearch/hermes-agent"
        self.status = {
            "schema_version": self.hermes.SCHEMA_VERSION,
            "run_key": "fake", "repo": self.repo, "fork": "test/fork",
            "issue": 123, "branch": "fixture", "worktree": str(self.root),
            "base": "main", "remote": "origin", "state": "READY_FOR_PUSH",
            "test_cmd": "python3 -m unittest", "allow_push": False,
            "created_at": "2026-10-11T00:00:00Z", "updated_at": "2026-10-11T00:00:00Z",
            "head": {"sha": self.sha, "at": "2026-10-11T00:00:00Z"},
            "red": {"ok": True, "at": "2026-10-11T00:00:00Z", "rc": 1,
                    "evidence": "logs/red-fixture.log", "cmd": "false"},
            "verify": {"ok": True, "at": "2026-10-11T00:00:00Z", "rc": 0,
                       "evidence": "logs/verify-fixture.log", "cmd": "true"},
            "review": {"ok": True, "at": "2026-10-11T00:00:00Z",
                       "verdict": "approve", "blockers": [], "reviewed_sha": self.sha,
                       "github_read": True, "stale": False, "nonce_ok": True},
            "push": {"allowed": False, "approved": False, "at": None,
                     "remote": "origin", "branch": "fixture"},
            "history": [], "attempts": [],
        }

    def run_local(self):
        self.assertEqual(self.hermes.validate_status(self.status), [])
        self.hermes.save_status(self.root, self.status)
        self.hermes.update_acceptance(self.root, self.status)
        acceptance = json.loads((self.h/"acceptance.json").read_text())
        self.assertEqual(self.hermes.validate_acceptance(acceptance), [])
        base = {
            "status": "SNAPSHOT_MATCH_ONLY", "reasons": [], "local_head": self.sha,
            "not_verified": ["CI"], "public_actions_authorized": False,
        }
        with patch.object(verify_hermes_run, "collect", return_value=base):
            return verify_hermes_run.audit(self.repo, 123, str(self.root))

    def test_genuine_hermes_schema_read(self):
        r = self.run_local()
        self.assertEqual(r["status"], "RECORDED_GATES_MATCH_UNTRUSTED")
        self.assertFalse(r["public_actions_authorized"])
        self.assertFalse(r["hermes_gates"]["independent_test_execution_verified"])

    def test_genuine_hermes_recorded_failure_blocks(self):
        self.status["verify"]["rc"] = 1
        self.assertIn("hermes_verify_exit_not_zero", self.run_local()["reasons"])

    def test_genuine_hermes_review_stale_blocks(self):
        self.status["review"]["reviewed_sha"] = "b" * 40
        self.assertIn("hermes_reviewed_head_mismatch", self.run_local()["reasons"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
