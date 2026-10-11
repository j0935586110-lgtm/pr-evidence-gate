#!/usr/bin/env python3
"""Deterministic, no-network tests for the isolated PR evidence gate."""
import importlib.util
import io
import json
import pathlib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

FILE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "pr_evidence.py"
spec = importlib.util.spec_from_file_location("pr_evidence", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
REPO = "NousResearch/hermes-agent"
HEAD = "a" * 40
OTHER = "b" * 40


class FakeRunner:
    def __init__(self, remote=None, local=HEAD, dirty="", failure=None):
        self.remote = remote if remote is not None else {
            "number": 99053, "state": "OPEN", "headRefOid": HEAD,
            "updatedAt": "2026-10-11T00:00:00Z"}
        self.local = local
        self.dirty = dirty
        self.failure = failure
        self.commands = []

    def __call__(self, argv, **kwargs):
        self.commands.append(argv)
        assert isinstance(argv, list), "shell string execution forbidden"
        assert kwargs.get("timeout") == 30
        if self.failure == argv[0]:
            return subprocess.CompletedProcess(argv, 17, "", "secret should not leak")
        if argv[0] == "gh":
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.remote), "")
        if argv[-2:] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(argv, 0, self.local + "\n", "")
        if argv[-3:] == ["status", "--porcelain=v1", "-uall"]:
            return subprocess.CompletedProcess(argv, 0, self.dirty, "")
        raise AssertionError("unexpected argv " + str(argv))


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_gate(self, engine=None, repo=REPO, pr=99053):
        return mod.collect(repo, pr, self.tmp.name, runner=engine or FakeRunner())

    def test_clean_exact_head_never_approves_publication(self):
        result = self.run_gate()
        self.assertEqual(result["status"], "SNAPSHOT_MATCH_ONLY")
        self.assertFalse(result["public_actions_authorized"])

    def test_dirty_change_blocks(self):
        result = self.run_gate(FakeRunner(dirty=" M agent/runtime_override.py\n"))
        self.assertIn("dirty_worktree", result["reasons"])
        self.assertEqual(result["local_modified_count"], 1)

    def test_untracked_file_blocks(self):
        result = self.run_gate(FakeRunner(dirty="?? accidental_secret.txt\n"))
        self.assertIn("dirty_worktree", result["reasons"])

    def test_remote_sha_advance_blocks(self):
        result = self.run_gate(FakeRunner(local=OTHER))
        self.assertIn("head_mismatch", result["reasons"])

    def test_nonopen_pr_blocks(self):
        result = self.run_gate(FakeRunner(remote={
            "number": 99053, "state": "CLOSED", "headRefOid": HEAD
        }))
        self.assertIn("remote_pr_not_open", result["reasons"])

    def test_wrong_pr_identity_blocks(self):
        result = self.run_gate(FakeRunner(remote={
            "number": 2, "state": "OPEN", "headRefOid": HEAD
        }))
        self.assertIn("remote_pr_identity_mismatch", result["reasons"])

    def test_missing_remote_head_blocks(self):
        result = self.run_gate(FakeRunner(remote={
            "number": 99053, "state": "OPEN", "headRefOid": None
        }))
        self.assertIn("missing_exact_remote_head", result["reasons"])

    def test_malformed_sha_blocks(self):
        result = self.run_gate(FakeRunner(local="bad"))
        self.assertIn("missing_exact_local_head", result["reasons"])

    def test_invalid_repo_rejected_before_runner(self):
        engine = FakeRunner()
        with self.assertRaises(ValueError):
            self.run_gate(engine, repo="owner; curl evil")
        self.assertEqual(engine.commands, [])

    def test_negative_pr_rejected_before_runner(self):
        engine = FakeRunner()
        with self.assertRaises(ValueError):
            self.run_gate(engine, pr=-4)
        self.assertEqual(engine.commands, [])

    def test_read_failure_does_not_echo_stderr(self):
        with self.assertRaisesRegex(RuntimeError, "read command failed"):
            self.run_gate(FakeRunner(failure="gh"))

    def test_no_shell_calls_or_publishing_commands(self):
        engine = FakeRunner()
        self.run_gate(engine)
        all_args = "\n".join(" ".join(a) for a in engine.commands)
        self.assertEqual(len(engine.commands), 3)
        for bad in ("push", "merge", "comment", "review", "pr create", "shell=True"):
            self.assertNotIn(bad, all_args)
        self.assertIn("gh pr view", all_args)

    def test_missing_workspace_rejected(self):
        with self.assertRaises(ValueError):
            mod.collect(REPO, 99053, self.tmp.name + "-missing", FakeRunner())

    def test_bool_not_accepted_as_pr_number(self):
        with self.assertRaises(ValueError):
            self.run_gate(pr=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
