#!/usr/bin/env python3
"""Read-only PR identity / local Git gate. No publishing permission is issued.

All repository / pull request inputs are arguments, never shell fragments.
This reports only a snapshot. It is NOT an independent test or CI verdict.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def call(runner, argv, cwd=None):
    result = runner(
        argv, cwd=cwd, capture_output=True, text=True, timeout=30,
        env=None,
    )
    if result.returncode:
        raise RuntimeError("read command failed: " + argv[0] + " exit=" + str(result.returncode))
    return result.stdout


def collect(repo: str, pr: int, worktree: str, runner=subprocess.run) -> dict:
    if not isinstance(repo, str) or not REPO_RE.fullmatch(repo):
        raise ValueError("invalid repository")
    if type(pr) is not int or pr < 1:
        raise ValueError("invalid PR number")
    path = Path(worktree).expanduser().resolve()
    if not path.is_dir():
        raise ValueError("worktree directory does not exist")
    read_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    remote = json.loads(call(
        runner, ["gh", "pr", "view", str(pr), "-R", repo, "--json",
                 "number,state,headRefOid,updatedAt"]
    ))
    head = remote.get("headRefOid")
    local = call(runner, ["git", "-c", "core.hooksPath=/dev/null",
                          "-C", str(path), "rev-parse", "HEAD"]).strip()
    dirty = call(runner, ["git", "-c", "core.hooksPath=/dev/null",
                          "-C", str(path), "status", "--porcelain=v1", "-uall"])
    reasons = []
    if remote.get("number") != pr:
        reasons.append("remote_pr_identity_mismatch")
    if remote.get("state") != "OPEN":
        reasons.append("remote_pr_not_open")
    if not isinstance(head, str) or not SHA_RE.fullmatch(head):
        reasons.append("missing_exact_remote_head")
    if not SHA_RE.fullmatch(local):
        reasons.append("missing_exact_local_head")
    if SHA_RE.fullmatch(local) and isinstance(head, str) and head != local:
        reasons.append("head_mismatch")
    if dirty.strip():
        reasons.append("dirty_worktree")
    return {
        "schema_version": 1, "read_at_utc": read_at,
        "repository": repo, "pr": pr, "worktree": str(path),
        "remote_head": head, "remote_updated_at": remote.get("updatedAt"),
        "local_head": local, "local_dirty": bool(dirty.strip()),
        "local_modified_count": len([x for x in dirty.splitlines() if x.strip()]),
        "status": "BLOCKED" if reasons else "SNAPSHOT_MATCH_ONLY",
        "reasons": reasons,
        "verified": ["github_cli_current_pr_metadata", "git_current_head", "git_porcelain_status"],
        "not_verified": ["CI", "test_execution", "review_authenticity", "sandbox", "authorization"],
        "public_actions_authorized": False,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--worktree", required=True)
    args = ap.parse_args(argv)
    try:
        result = collect(args.repo, args.pr, args.worktree)
    except (ValueError, RuntimeError, json.JSONDecodeError, OSError, subprocess.TimeoutExpired) as exc:
        # Never copy subprocess stderr: it may contain credentials.
        result = {"schema_version": 1, "status": "ERROR",
                  "reason": str(exc)[:220], "public_actions_authorized": False}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return {"SNAPSHOT_MATCH_ONLY": 0, "BLOCKED": 2, "ERROR": 3}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
