# Independent evidence bundle — NousResearch/hermes-agent PR #98703

**Published as a reproducible evidence snapshot; publication of this package is not a GitHub PR review or approval.** All claims here are scoped to the exact head 877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645. This is a redacted copy of raw local receipts, not a hosted upstream CI artifact.

## Decision at a glance

- **Tests independently executed via J1 on Linux:** 25 changed test files, **287 passed, 0 failed, 2 skipped** (the skipped tests are macOS-only `scutil` proxy cache tests). Canonical `scripts/run_tests.sh` exit code **0**; Python 3.14.7, pytest 9.1.1, `uv.lock` dev+test dependencies.
- **Code health independent execution:** at pre-fix 14f49cbfa, `python scripts/check --only health` exit **1**, **11 blocking**. At current 877f0ecbf, the **same** `--only health` check returned exit **0**, **0 blocking / 0 advisory**; the full `python scripts/check` also returned exit **0**, **11 checks ok**. Both health-only receipts use merge-base 302c5d9f6793.
- **Contributor attribution:** locally replayed the logic from `.github/workflows/contributor-check.yml`. At pre-fix head, missing contributors include Oleg plus **three unrelated preexisting upstream author identities**. At the GitHub-provided `refs/pull/98703/merge` checkout 48a375f33, the in-scope two authors are mapped and the check **PASS**. Different merge-base ranges are intentional; do not misstate this as exact-head hosted CI green.
- **Snapshot integrity:** PR Evidence Gate matched current GitHub head to a clean local worktree; result `SNAPSHOT_MATCH_ONLY`. It explicitly **does not** attest test execution, hosted CI, safety, or approval.
- **Supplemental AI-assisted review:** paid DSH and AGY Claude were instructed separately by the same operator. Their reports are **not included in this publication bundle as externally auditable proof**. Earlier speculative P1/P2 hypotheses were downgraded after examining production callers. These analyses cannot substitute for executed receipts or maintainer review.

## Traceability

| Object | Immutable identity |
|---|---|
| PR source HEAD | `877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645` |
| Comparison base | `302c5d9f679333ae957c256d76a3dff35120f4e0` |
| Pre-fix head | `14f49cbfa3d4ca55a7ee13031724a1d9416f8466` |
| GitHub-provided PR merge ref for attribution reproduction | `48a375f33aabf8fe901fa1ff0a66f5fbfffdc5df` |
| Upstream main parent of that merge | `0faf0938ebdc4420e11070822cf4f9db09eb4260` |
| Head Git tree SHA (E3 and i5 checkout) | `2cca73774a32467135b529948e7eb2f3693be5b2` |
| Unredacted E3 test log SHA-256 | `45c2624c43d04d28fe97027bdd3f22cb3d045e72a3a83689b4619e36540f9262` |
| Linux test report | `logs/25-changed-files-Linux-py314.log` |
| Code health before / after, matched flag | `logs/code-health-before.log` and `logs/code-health-current-health-only.log` |
| Full code checks at head | `logs/code-health-current.log` |
| Exact-head J1 test/checkout coupling | `logs/exact-head-provenance-9tests.log` (nine quiet image tests; SHA/tree/dirty before and after) |
| Blocker source references | `FINDINGS-TRACE.md` |
| Contributor mapping before / after merge | `logs/contributor-before.log` and `logs/contributor-merge-reproduction.log` |
| List of changed Python tests | `tests/changed-test-files.txt` |
| Full filename hashes | `manifest.json` |

## Important limitations

1. **Upstream GitHub Actions exact-head CI remains `action_required`** (runs awaiting maintainer action). There are **no hosted green CI run URLs for this exact head** in this bundle.
2. Two macOS-only tests skipped on Linux; no independent macOS execution receipt. The full repository suite was not run.
3. Before the fixes there were **six FILE_LINES blockers**, of which **two were handled through code/test extraction**, and **four now use header waivers with written reasons**. Local health passes, but maintainers must assess whether those reasons are acceptable.
4. The contributor check is **a local reproduction of the workflow logic**, not an official GitHub Actions completed run.
5. The test container had no git, resulting in a nonfatal `git: command not found` from optional compileall. The 25-file runner still returned exit 0. To strengthen exact-head provenance, a **separate focused 9-test rerun** records the E3 host HEAD/tree/dirty state before and after launching the isolated container, plus the test exit code, all in one original command receipt. The 287-test log itself still does not contain a git SHA printed inside the container; the source mount and host checkout identity are reconstructed from J1 operations rather than independently attested by hosted CI.
6. This archive intentionally lacks API tokens, user secrets, personal path names, and exact private host details. Logs are **sanitized**: the log bytes inside the bundle have hashes different from their originals. See manifest.json for both hashes. A reviewer can reproduce runs but cannot verify the raw originals unless they are separately made available.
7. **Nothing in this bundle proves production provider I/O or full security.** Synthetic/mock tests cannot certify every live provider.

## Links (public GitHub objects, not private receipts)

- [PR #98703](https://github.com/NousResearch/hermes-agent/pull/98703)
- [Reviewer asks for actual receipts](https://github.com/NousResearch/hermes-agent/pull/98703#issuecomment-6089860562)
- [PR Evidence Gate repository](https://github.com/j0935586110-lgtm/pr-evidence-gate) — this separate evidence-tool project is NOT the PR #98703 CI.

See `REPRODUCE.md` for commands and `REVIEW-DRAFT-NOT-POSTED.md` for a proposed evidence-backed comment.
