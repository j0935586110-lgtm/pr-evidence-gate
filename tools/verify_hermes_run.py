#!/usr/bin/env python3
"""Audit Hermes' existing run artifacts and current GitHub PR identity, read-only.

Do not interpret a PASS as a permission to push or merge; logs and status
may originate from agents. Independent trusted tests are a separate gate.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path

from pr_evidence import collect

READY = {"READY_FOR_PUSH", "AWAITING_HUMAN_PR"}


def read_json(path: Path) -> dict:
    # Open the actual file descriptor before checking size: stat(path) followed
    # by read_text(path) would permit a file swap/race between those operations.
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("Hermes artifact must be a regular file")
        # Bound the read even if another process grows the file after fstat.
        raw = handle.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("Hermes artifact too large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def audit(repo: str, pr: int, worktree: str, runner=None) -> dict:
    root = Path(worktree).expanduser().resolve()
    hermes = root / ".hermes"
    base = collect(repo, pr, str(root), runner=runner) if runner else collect(repo, pr, str(root))
    reasons = list(base["reasons"])
    evidence = {}
    if hermes.is_symlink() or not hermes.resolve().is_relative_to(root):
        return {**base, "status": "BLOCKED",
                "reasons": reasons + ["hermes_directory_unsafe"],
                "hermes_gates": evidence, "public_actions_authorized": False}
    try:
        status = read_json(hermes / "status.json")
        acceptance = read_json(hermes / "acceptance.json")
    except (OSError, ValueError, json.JSONDecodeError):
        reasons.append("missing_or_invalid_hermes_artifacts")
        return {**base, "status": "BLOCKED", "reasons": reasons,
                "hermes_gates": evidence, "public_actions_authorized": False}
    sha = base["local_head"]
    if status.get("repo") != repo:
        reasons.append("hermes_repo_mismatch")
    if status.get("worktree") != str(root):
        reasons.append("hermes_worktree_mismatch")
    if status.get("state") not in READY:
        reasons.append("hermes_run_not_ready")
    head = status.get("head")
    if not isinstance(head, dict) or head.get("sha") != sha:
        reasons.append("hermes_recorded_head_mismatch")
    for gate in ("red", "verify", "review"):
        node = status.get(gate)
        if not isinstance(node, dict) or node.get("ok") is not True:
            reasons.append("hermes_" + gate + "_not_passed")
        else:
            if gate == "verify" and node.get("rc") != 0:
                reasons.append("hermes_verify_exit_not_zero")
            if gate == "review" and node.get("reviewed_sha") != sha:
                reasons.append("hermes_reviewed_head_mismatch")
            if gate == "review" and (node.get("verdict") != "approve" or
                                     node.get("blockers") or
                                     node.get("github_read") is not True):
                reasons.append("hermes_review_not_approved")
    gates = acceptance.get("gates")
    if not isinstance(gates, dict):
        reasons.append("missing_acceptance_gates")
    else:
        for name in ("red_evidence", "tests_pass", "head_match", "review_approved"):
            node = gates.get(name)
            if not isinstance(node, dict) or node.get("ok") is not True:
                reasons.append("acceptance_" + name + "_not_passed")
    if acceptance.get("repo") != repo:
        reasons.append("acceptance_repo_mismatch")
    # Local artifacts are only agent-reported evidence, never proof of secure execution.
    for gate in ("red", "verify"):
        node = status.get(gate, {})
        reported = node.get("evidence") if isinstance(node, dict) else None
        if not isinstance(reported, str) or not reported:
            reasons.append("missing_" + gate + "_log")
            continue
        target = (hermes / reported).resolve()
        if not target.is_relative_to(hermes.resolve()):
            reasons.append(gate + "_log_path_escape")
        elif not target.is_file() or target.stat().st_size == 0:
            reasons.append("missing_" + gate + "_log")
    verify_record = status.get("verify") if isinstance(status.get("verify"), dict) else {}
    review_record = status.get("review") if isinstance(status.get("review"), dict) else {}
    evidence = {
        "state": status.get("state"),
        "reported_verified": verify_record.get("ok"),
        "reported_reviewed_sha": review_record.get("reviewed_sha"),
        "reported_gate_origin": "agent_artifacts_untrusted",
        "independent_test_execution_verified": False,
    }
    return {
        **base,
        "status": "BLOCKED" if reasons else "RECORDED_GATES_MATCH_UNTRUSTED",
        "reasons": reasons, "hermes_gates": evidence,
        "public_actions_authorized": False,
        "not_verified": sorted(set(base["not_verified"] + [
            "trusted_test_execution", "trusted_review",
            "sandbox_and_credentials", "release_authorization",
        ])),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--worktree", required=True)
    args = ap.parse_args(argv)
    try:
        result = audit(args.repo, args.pr, args.worktree)
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        result = {"status": "ERROR", "reason": type(exc).__name__,
                  "public_actions_authorized": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {"RECORDED_GATES_MATCH_UNTRUSTED": 0, "BLOCKED": 2, "ERROR": 3}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
