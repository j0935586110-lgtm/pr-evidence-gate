#!/usr/bin/env python3
"""Offline, read-only artifact receipt integrity check (not an attestation).

The receipt and logs are UNTRUSTED local assertions. This verifier never runs
the commands named in them, authenticates the author or authorizes publishing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat

from pr_evidence import REPO_RE, SHA_RE, collect
from verify_hermes_run import read_json

SCHEMA = "pr-evidence-gate/receipt/v1"
OUTCOMES = frozenset({
    "PASS", "REPRODUCED", "EXPECTED_FAILURE", "FAIL", "ACTION_REQUIRED", "NOT_RUN",
})
PHASES = frozenset({"before", "after", "mainline", "hosted_ci"})
MAX_CHECKS = 100
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


class ReceiptError(ValueError):
    """A fail-closed receipt or artifact integrity violation."""


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ReceiptError(field + "_invalid")
    return value


def _relative_artifact(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not (0 < len(value) <= 512):
        raise ReceiptError("artifact_path_invalid")
    if PureWindowsPath(value).is_absolute():
        raise ReceiptError("artifact_path_escape")
    if "\\" in value or "\x00" in value:
        raise ReceiptError("artifact_path_invalid")
    posix = PurePosixPath(value)
    if posix.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise ReceiptError("artifact_path_escape")
    current = root
    for part in posix.parts:
        current = current / part
        # Do not follow any symlink, including intermediate directories.
        if current.is_symlink():
            raise ReceiptError("artifact_symlink_rejected")
    if not current.resolve().is_relative_to(root):
        raise ReceiptError("artifact_path_escape")
    return current


def _hash_file(path: Path, limit: int) -> tuple[str, int]:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ReceiptError("artifact_not_regular_file")
    if before.st_size <= 0 or before.st_size > limit:
        raise ReceiptError("artifact_size_invalid")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as f:
        opened = os.fstat(f.fileno())
        if (not stat.S_ISREG(opened.st_mode) or
            (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise ReceiptError("artifact_identity_changed")
        digest = hashlib.sha256()
        consumed = 0
        while True:
            block = f.read(min(65536, limit - consumed + 1))
            if not block:
                break
            consumed += len(block)
            if consumed > limit:
                raise ReceiptError("artifact_too_large")
            digest.update(block)
        after = os.fstat(f.fileno())
        if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns
        ):
            raise ReceiptError("artifact_changed_during_read")
    return digest.hexdigest(), consumed


def inspect(manifest: str | Path, *, worktree: str | None = None) -> dict:
    """Check receipt schema and hashed local files; optionally pin remote PR HEAD."""
    source = Path(manifest).expanduser().absolute()
    result = {
        "schema": "pr-evidence-gate/receipt-check/v1",
        "status": "BLOCKED", "reasons": [], "artifact_count": 0,
        "source_trust": "self_reported_untrusted",
        "test_execution_verified": False,
        "review_authenticity_verified": False,
        "hosted_ci_verified": False,
        "safe_to_publish": False,
        "mutating_actions_supported": False,
        "snapshot_status": "NOT_CHECKED",
    }
    try:
        record = read_json(source)
        if record.get("schema") != SCHEMA:
            raise ReceiptError("unsupported_receipt_schema")
        repo = record.get("repository")
        pr = record.get("pr")
        if not isinstance(repo, str) or not REPO_RE.fullmatch(repo):
            raise ReceiptError("repository_invalid")
        if type(pr) is not int or pr <= 0:
            raise ReceiptError("pr_invalid")
        head = _sha(record.get("head_sha"), "head_sha")
        if "baseline_sha" in record:
            _sha(record["baseline_sha"], "baseline_sha")
        entries = record.get("checks")
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_CHECKS:
            raise ReceiptError("checks_invalid")
        root = source.parent.resolve()
        seen = set()
        total_bytes = 0
        matched = 0
        current_head_after = False
        hosted_ci_pending = False
        for item in entries:
            if not isinstance(item, dict):
                raise ReceiptError("check_invalid")
            ident = item.get("id")
            if not isinstance(ident, str) or not 1 <= len(ident) <= 80 or ident in seen:
                raise ReceiptError("check_id_invalid_or_duplicate")
            seen.add(ident)
            phase, outcome = item.get("phase"), item.get("outcome")
            if phase not in PHASES or outcome not in OUTCOMES:
                raise ReceiptError("check_phase_or_outcome_invalid")
            source_sha = _sha(item.get("source_sha"), "source_sha")
            platform = item.get("platform")
            if not isinstance(platform, str) or not 1 <= len(platform) <= 96:
                raise ReceiptError("check_platform_invalid")
            evidence, rc = item.get("artifact"), item.get("exit_code")
            if outcome in ("NOT_RUN", "ACTION_REQUIRED"):
                if evidence is not None or rc is not None:
                    raise ReceiptError("unexecuted_check_claims_execution")
                if not isinstance(item.get("reason"), str) or not item["reason"].strip():
                    raise ReceiptError("unexecuted_check_missing_reason")
            else:
                if phase == "hosted_ci":
                    raise ReceiptError("hosted_ci_not_trusted_from_local_log")
                if type(rc) is not int:
                    raise ReceiptError("exit_code_invalid")
                if (outcome in ("PASS", "REPRODUCED") and rc != 0) or (
                    outcome in ("EXPECTED_FAILURE", "FAIL") and rc == 0
                ):
                    raise ReceiptError("outcome_exit_code_mismatch")
                if not isinstance(evidence, dict):
                    raise ReceiptError("artifact_missing")
                path = _relative_artifact(root, evidence.get("path"))
                claimed_digest = evidence.get("sha256")
                if (not isinstance(claimed_digest, str) or len(claimed_digest) != 64 or
                    any(c not in "0123456789abcdef" for c in claimed_digest)):
                    raise ReceiptError("artifact_digest_invalid")
                claimed_size = evidence.get("bytes")
                if type(claimed_size) is not int or not 0 < claimed_size <= MAX_ARTIFACT_BYTES:
                    raise ReceiptError("artifact_size_invalid")
                actual_digest, size = _hash_file(path, MAX_ARTIFACT_BYTES)
                if actual_digest != claimed_digest or size != claimed_size:
                    raise ReceiptError("artifact_hash_or_size_mismatch")
                matched += 1
                total_bytes += size
                if total_bytes > MAX_TOTAL_BYTES:
                    raise ReceiptError("receipt_total_bytes_exceeded")
                if phase == "after" and source_sha == head and outcome == "PASS":
                    current_head_after = True
            if phase == "hosted_ci" and outcome != "PASS":
                hosted_ci_pending = True

        result.update({
            "repository": repo, "pr": pr, "head_sha": head,
            "artifact_count": matched, "artifact_bytes": total_bytes,
            "recorded_check_count": len(entries),
            "current_head_after_test_reported": current_head_after,
            "hosted_ci_pending_or_unverified": hosted_ci_pending,
            "status": "HASHES_MATCH_UNTRUSTED",
        })
        # A hash match establishes artifact integrity relative to the supplied
        # receipt, NOT truthfulness, code execution, CI or author identity.
        if worktree is not None:
            snap = collect(repo, pr, worktree)
            result["snapshot_status"] = snap["status"]
            if snap["status"] != "SNAPSHOT_MATCH_ONLY" or snap.get("local_head") != head:
                result["status"] = "BLOCKED"
                result["reasons"].append("remote_or_local_head_mismatch")
        return result
    except (ReceiptError, ValueError, OSError, json.JSONDecodeError) as exc:
        result["reasons"].append(
            str(exc) if isinstance(exc, ReceiptError) else "unreadable_or_invalid_receipt"
        )
        return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--worktree",
                        help="Optional: also check exact current GitHub PR HEAD via gh")
    args = parser.parse_args(argv)
    try:
        result = inspect(args.manifest, worktree=args.worktree)
        rc = 0 if result["status"] == "HASHES_MATCH_UNTRUSTED" else 2
    except Exception as exc:
        # Hide arbitrary stderr/path values from external subprocesses.
        result = {"schema": "pr-evidence-gate/receipt-check/v1",
                  "status": "ERROR", "reason": type(exc).__name__,
                  "safe_to_publish": False, "mutating_actions_supported": False}
        rc = 3
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
