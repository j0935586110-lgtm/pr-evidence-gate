#!/usr/bin/env python3
"""Offline, fail-closed dual-mode workflow dispatch tests."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import pr_workflow as flow

class WorkflowTests(unittest.TestCase):
    def test_maintainer_reuses_live_snapshot(self):
        result={"status":"SNAPSHOT_MATCH_ONLY","reasons":[]}
        with patch.object(flow,"collect",return_value=result) as target:
            res=flow.evaluate("maintainer","a/b",3,"/tmp/x")
        target.assert_called_once_with("a/b",3,"/tmp/x")
        self.assertEqual(res["layer"],"github_and_git_snapshot")
        self.assertFalse(res["safe_to_publish"])
        self.assertFalse(res["mutating_actions_supported"])

    def test_contributor_reuses_hermes_recorded_artifacts(self):
        result={"status":"RECORDED_GATES_MATCH_UNTRUSTED","reasons":[]}
        with patch.object(flow,"audit",return_value=result) as target:
            res=flow.evaluate("contributor","a/b",3,"/tmp/x")
        target.assert_called_once_with("a/b",3,"/tmp/x")
        self.assertEqual(res["layer"],"github_git_and_hermes_recorded_artifacts")
        self.assertFalse(res["safe_to_publish"])

    def test_dirty_snapshot_always_blocks(self):
        with patch.object(flow,"collect",return_value={"status":"BLOCKED","reasons":["dirty_worktree"]}):
            res=flow.evaluate("maintainer","a/b",3,"/tmp/x")
        self.assertEqual(res["next_step"],"resolve_blockers")

    def test_stale_head_always_blocks(self):
        with patch.object(flow,"audit",return_value={"status":"BLOCKED","reasons":["head_mismatch"]}):
            res=flow.evaluate("contributor","a/b",3,"/tmp/x")
        self.assertFalse(res["safe_to_publish"])

    def test_unknown_mode_blocks_before_tools(self):
        with patch.object(flow,"collect") as c, patch.object(flow,"audit") as a:
            with self.assertRaises(ValueError):
                flow.evaluate("publisher","a/b",1,".")
            c.assert_not_called()
            a.assert_not_called()

    def test_cli_blocked_exit_code(self):
        with patch.object(flow,"evaluate",return_value={"result":{"status":"BLOCKED"}}):
            with patch("sys.stdout"):
                rc=flow.main(["--mode","maintainer","--repo","a/b","--pr","12","--worktree","."])
        self.assertEqual(rc,2)

    def test_cli_snapshot_match_requires_human(self):
        with patch.object(flow,"evaluate",return_value={"result":{"status":"SNAPSHOT_MATCH_ONLY"}}):
            with patch("sys.stdout"):
                rc=flow.main(["--mode","maintainer","--repo","a/b","--pr","12","--worktree","."])
        self.assertEqual(rc,0)

    def test_cli_exception_is_fail_closed(self):
        with patch.object(flow,"evaluate",side_effect=RuntimeError("SECRET_FAIL")):
            with patch("sys.stdout"):
                rc=flow.main(["--mode","maintainer","--repo","a/b","--pr","12","--worktree","."])
        self.assertEqual(rc,3)

if __name__=="__main__":
    unittest.main()
