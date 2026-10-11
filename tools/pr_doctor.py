#!/usr/bin/env python3
"""Portable, non-mutating dependency/checkout diagnostics for PR Evidence Gate.

No network writes, no token printing, no executing code from target repositories.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable


def inspect(
    mode: str = "maintainer",
    worktree: str | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable = subprocess.run,
) -> dict:
    if mode not in ("maintainer", "contributor"):
        raise ValueError("invalid mode")
    checks = []
    def check(name: str, ok: bool, fix: str, required: bool = True) -> None:
        checks.append({"id": name, "ok": bool(ok), "required": required,
                       "fix": None if ok else fix})

    py_ok = sys.version_info >= (3, 10)
    check("python", py_ok, "Install Python 3.10+: https://www.python.org/downloads/")
    git = which("git")
    gh = which("gh")
    check("git", bool(git), "Install Git: https://git-scm.com/downloads")
    check("github_cli", bool(gh), "Install GitHub CLI: https://cli.github.com/")
    auth_ok = False
    if gh:
        try:
            # Discard all CLI output. gh auth status may print credential metadata.
            result = run([gh, "auth", "status", "--hostname", "github.com"],
                         capture_output=True, text=True, timeout=10)
            auth_ok = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    check("github_auth", auth_ok, "Run: gh auth login --hostname github.com")
    if worktree:
        root = Path(worktree).expanduser().resolve()
        checkout_ok = False
        if root.is_dir() and git:
            try:
                p = run([git, "-c", "core.hooksPath=/dev/null", "-C", str(root),
                         "rev-parse", "--is-inside-work-tree"],
                        capture_output=True, text=True, timeout=10)
                checkout_ok = p.returncode == 0 and p.stdout.strip() == "true"
            except (OSError, subprocess.TimeoutExpired):
                pass
        check("pr_checkout", checkout_ok,
              "Provide --worktree pointing to a real checkout of the PR commit.")
        if mode == "contributor":
            records = (root / ".hermes" / "status.json").is_file() and (
                root / ".hermes" / "acceptance.json").is_file()
            check("hermes_evidence", records,
                  "Contributor mode needs existing .hermes/status.json and .hermes/acceptance.json; "
                  "otherwise use --mode maintainer.")
    else:
        check("pr_checkout", False,
              "Pass --worktree /path/to/a/local-PR-checkout for a full environment check.",
              required=False)
        if mode == "contributor":
            check("hermes_evidence", False,
                  "Use --worktree to check whether Hermes evidence files exist.",
                  required=False)
    required_missing = [x["id"] for x in checks if x["required"] and not x["ok"]]
    return {"schema": "pr-evidence-gate/doctor/v1",
            "status": "READY_FOR_METADATA_CHECK" if not required_missing else "BLOCKED",
            "mode": mode, "checks": checks, "missing": required_missing,
            "snapshot_only": True, "public_actions_authorized": False}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("maintainer", "contributor"),
                        default="maintainer")
    parser.add_argument("--worktree")
    a = parser.parse_args(argv)
    report = inspect(a.mode, a.worktree)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "READY_FOR_METADATA_CHECK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
