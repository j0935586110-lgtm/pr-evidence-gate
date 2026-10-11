# Evidence receipts (v0.3.0)

A read-only, stdlib-only *integrity filter* for PR test receipts. It does **not**
run tests, authenticate testers, verify cryptographic attestations, or approve
publishing. A forged log plus a matching forged hash will still pass.

## Two independent gates

1. `pr-evidence-gate check --repo OWNER/REPO --pr N --worktree PATH`:
   live GitHub PR head against the local clean checkout, via `gh`.
2. `pr-evidence-gate receipt --manifest PATH [--worktree PATH]`:
   receipt schema + SHA-256 and byte size of each named local artifact.
   With `--worktree`, also check the current remote PR head using `gh`.

`receipt` works **offline** without `gh` when no worktree is supplied.
It returns `HASHES_MATCH_UNTRUSTED` on consistency, which is **not a GO**.
A missing/tampered file or stale HEAD is `BLOCKED`.

Try a **synthetic, nonproduction** example included in this repository:

```bash
python -m pip install .
pr-evidence-gate receipt --manifest examples/receipt-v1/receipt.json
```

For a real PR:

```bash
pr-evidence-gate check --mode maintainer \
  --repo NousResearch/hermes-agent --pr 99053 --worktree /path/to/pinned-checkout

# In the same separately-pinned verified checkout:
pr-evidence-gate receipt --manifest /path/to/receipts/receipt.json \
  --worktree /path/to/pinned-checkout
```

If the PR head advances, the snapshot check fails closed. Note that
untracked receipt files inside `--worktree` make its normal Git status dirty:
keep receipt logs in a **separate** directory outside the clean checkout.

## Receipt schema

`schema`: `pr-evidence-gate/receipt/v1`

Top-level: `repository` (OWNER/REPO), `pr` (integer), `head_sha` (40
lowercase hex), optional `baseline_sha`, `checks` (array, 1–100).

Each check: `id` (unique), `phase` (`before` | `after` | `mainline` |
`hosted_ci`), `source_sha` (commit actually tested), `platform`, `outcome`,
`exit_code`, and—**only for executed local checks**—`artifact`:
`{"path": "logs/after.log", "sha256": "64lowercasehex", "bytes": 123}`.
The artifact path is relative to the receipt's parent directory. No absolute
paths, `..`, backslash, or symlinked files / path components are accepted.

| Outcome | Meaning | Exit code | Artifact |
|---|---|---|---|
| `EXPECTED_FAILURE` | Before fix: known negative repro returned nonzero | nonzero | Required |
| `REPRODUCED` | Witness test passed **by reproducing a bug** | 0 | Required |
| `PASS` | Recorded local test finished successfully | 0 | Required |
| `FAIL` | Recorded local test failed | nonzero | Required |
| `ACTION_REQUIRED` | Hosted CI unapproved/blocked | null | None; `reason` required |
| `NOT_RUN` | No test performed | null | None; `reason` required |

The `source_sha` **must be the actual tested revision**. In the Hermes
#99053 example, some macOS tests exercised the pre-merge *candidate* but not
the final merge Commit. Do not relabel them as final-head validation.
The response explicitly shows whether any `after` check claims to cover
`head_sha` and whether hosted CI is pending. These claims remain untrusted.

Limits: 1 MiB manifest, 16 MiB per artifact, 64 MiB aggregate, regular files
only, no symlinks (including directories). Files are hashed using bounded
reads and checked for changes while read. This is local integrity, **not a
remote timestamp, signature, tamper-proof log, or authoritative CI status**.

## #99053 public case study (not synthetic)

The standalone [Hermes upstream-main mismatch reproducer](https://github.com/j0935586110-lgtm/hermes-agent/blob/9dc1ad01ecd3d19f7f5fd2fb1b6d087371f5ed36/evals/test_middleware_model_identity_witness.py)
shows a model identity divergence on pinned main `97a9ae8...`. See the
[verification report](https://github.com/j0935586110-lgtm/hermes-agent/blob/9dc1ad01ecd3d19f7f5fd2fb1b6d087371f5ed36/docs/evidence/PR99053_MODEL_STATE_VERIFICATION_20261011.md)
and [upstream #99053 comment](https://github.com/NousResearch/hermes-agent/pull/99053#issuecomment-6110578052).
The case included Linux/macOS, before/after, local SHA-256 receipts, and
hosted CI `action_required` (NOT passed). That workflow informed this generic
format; **the synthetic example below is not presented as its real results**.

## Security and provenance boundary

Receipt logs are *user- or agent-supplied assertions*. Hash matches can catch
mistakes, lost files or subsequent modification; they cannot prove the command
ran, the output is honest, or the recorded SHA was really checked out.
Don't accept external PR contributor-supplied receipts as authoritative CI.
For remotely trusted build artifact provenance, use GitHub
[artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
and `gh attestation verify`; for authorized multistep supply-chain layouts,
consider [in-toto](https://in-toto.io/). This tool doesn't duplicate those.

The binary return code `0` means **metadata/hash consistency only**;
`2` means blocked; `3` means an operational error. Neither `0` nor
`HASHES_MATCH_UNTRUSTED` authorizes merge, push, review, publication or
production deployment. Fail closed on uncertainty.
