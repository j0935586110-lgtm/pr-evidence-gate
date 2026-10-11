#!/usr/bin/env python3
"""Read-only contributor/maintainer PR gate; delegates to existing tools.

No new task state; Hermes owns workflows, GitHub owns remote PR data.
This CLI cannot push, comment, approve, merge, or run untrusted PR code.
"""
from __future__ import annotations

import argparse
import json
import sys

from pr_doctor import inspect

from pr_evidence import collect
from verify_hermes_run import audit


def evaluate(mode: str, repo: str, pr: int, worktree: str) -> dict:
    if mode == "maintainer":
        result = collect(repo, pr, worktree)
        layer = "github_and_git_snapshot"
    elif mode == "contributor":
        result = audit(repo, pr, worktree)
        layer = "github_git_and_hermes_recorded_artifacts"
    else:
        raise ValueError("unknown PR workflow mode")
    return {
        "schema": "pr-dual-mode/v1",
        "mode": mode,
        "layer": layer,
        "result": result,
        "safe_to_publish": False,
        "mutating_actions_supported": False,
        "next_step": (
            "human_and_CI_verification_required"
            if result["status"] in ("SNAPSHOT_MATCH_ONLY", "RECORDED_GATES_MATCH_UNTRUSTED")
            else "resolve_blockers"
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("check", "doctor"),
                        default="check", help="doctor: diagnose setup; check: verify PR snapshot")
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.0")
    parser.add_argument("--mode", choices=("maintainer", "contributor"),
                        default="maintainer")
    parser.add_argument("--repo")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--worktree")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        output = inspect(args.mode, args.worktree)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output["status"] == "READY_FOR_METADATA_CHECK" else 2
    if not args.repo or not args.pr or not args.worktree:
        parser.error("check needs --repo OWNER/REPO, --pr NUMBER and --worktree PATH; try 'doctor' first")
    try:
        output = evaluate(args.mode, args.repo, args.pr, args.worktree)
        status = output["result"]["status"]
        rc = 0 if status in ("SNAPSHOT_MATCH_ONLY", "RECORDED_GATES_MATCH_UNTRUSTED") else 2
    except Exception as exc:
        # Never forward arbitrary GitHub stderr or credentials. Only provide
        # constant remediation strings for absent executable dependencies.
        missing = getattr(exc, "filename", None)
        dependency = str(missing).rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if missing else ""
        fix = None
        if isinstance(exc, FileNotFoundError):
            if dependency == "gh":
                fix = "Install GitHub CLI (https://cli.github.com/) and run gh auth login."
            elif dependency == "git":
                fix = "Install Git (https://git-scm.com/downloads)."
            else:
                fix = "Run pr-evidence-gate doctor --worktree PATH to check prerequisites."
        output = {
            "schema": "pr-dual-mode/v1",
            "mode": args.mode,
            "result": {"status": "ERROR", "reason": type(exc).__name__,
                       "fix": fix},
            "safe_to_publish": False,
            "mutating_actions_supported": False,
        }
        rc = 3
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
