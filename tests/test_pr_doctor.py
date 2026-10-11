"""Offline doctor and new-user CLI validation, no real GitHub/token access."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import pr_doctor as doc
import pr_workflow as flow

def runner(argv, **kw):
    if argv[:3]==["/usr/bin/gh","auth","status"]:
        return subprocess.CompletedProcess(argv,0,"secret token output","")
    if "rev-parse" in argv:
        return subprocess.CompletedProcess(argv,0,"true\n","")
    raise AssertionError("unexpected subprocess call")

class DoctorTests(unittest.TestCase):
    def test_missing_gh_is_actionable_and_blocked(self):
        def which(x):return {"git":"/usr/bin/git"}.get(x)
        d=doc.inspect(which=which,run=runner)
        self.assertEqual(d["status"],"BLOCKED")
        self.assertIn("github_cli",d["missing"])
        self.assertIn("github_auth",d["missing"])
        self.assertFalse(d["public_actions_authorized"])
        self.assertIn("cli.github.com",json.dumps(d))

    def test_authenticated_tools_are_ready_without_checkout(self):
        def which(x):return "/usr/bin/"+x
        d=doc.inspect(which=which,run=runner)
        self.assertEqual(d["status"],"READY_FOR_METADATA_CHECK")
        self.assertEqual(d["missing"],[])
        self.assertFalse(next(x for x in d["checks"] if x["id"]=="pr_checkout")["required"])

    def test_worktree_and_hermes_required_for_contributor(self):
        with tempfile.TemporaryDirectory() as td:
            d=doc.inspect("contributor",td,which=lambda x:"/usr/bin/"+x,run=runner)
            self.assertEqual(d["status"],"BLOCKED")
            self.assertIn("hermes_evidence",d["missing"])
            self.assertFalse(d["public_actions_authorized"])

    def test_invalid_checkout_blocks_but_not_access_tokens(self):
        d=doc.inspect("maintainer","/nonexistent-pr-evidence-gate-smoke",
                      which=lambda x:"/usr/bin/"+x,run=runner)
        self.assertIn("pr_checkout",d["missing"])
        self.assertNotIn("secret token output",json.dumps(d))

    def test_failed_auth_discard_cli_details(self):
        def fail(argv,**kw):
            return subprocess.CompletedProcess(argv,1,"TOKEN_SECRET_TEST","")
        d=doc.inspect(which=lambda x:"/usr/bin/"+x,run=fail)
        self.assertIn("github_auth",d["missing"])
        self.assertNotIn("TOKEN_SECRET_TEST",json.dumps(d))

    def test_cli_doctor_exit_status(self):
        with patch.object(flow,"inspect",return_value={"status":"BLOCKED","missing":["github_cli"]}):
            with patch("sys.stdout"):
                self.assertEqual(flow.main(["doctor"]),2)

    def test_cli_doctor_ready(self):
        with patch.object(flow,"inspect",return_value={"status":"READY_FOR_METADATA_CHECK"}):
            with patch("sys.stdout"):
                self.assertEqual(flow.main(["doctor","--mode","maintainer"]),0)

    def test_missing_github_cli_check_actionable(self):
        with patch.object(flow,"evaluate",side_effect=FileNotFoundError(2,"missing","gh")):
            from io import StringIO
            buf=StringIO()
            with patch("sys.stdout",buf):
                rc=flow.main(["check","--mode","maintainer","--repo","a/b","--pr","5","--worktree","."])
        out=json.loads(buf.getvalue())
        self.assertEqual(rc,3)
        self.assertEqual(out["result"]["reason"],"FileNotFoundError")
        self.assertIn("cli.github.com",out["result"]["fix"])
        self.assertFalse(out["safe_to_publish"])

    def test_invalid_mode_is_fail_closed(self):
        with self.assertRaises(ValueError):
            doc.inspect("publish",which=lambda x:None,run=runner)

if __name__=="__main__":
    unittest.main()
