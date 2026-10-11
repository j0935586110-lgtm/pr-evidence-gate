# macOS independent execution addendum — Hermes PR #98703

**Added 2026-10-11 after the existing Evidence-backed COMMENT review.**
This append-only note complements the original Linux results. It does **not** replace, edit, or approve the existing official GitHub review.

- **Source PR**: https://github.com/NousResearch/hermes-agent/pull/98703
- **Review (unchanged)**: https://github.com/NousResearch/hermes-agent/pull/98703#pullrequestreview-5483237359
- **Tested exact PR HEAD**: `877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645`
- **Git tree**: `2cca73774a32467135b529948e7eb2f3693be5b2`
- **Platform**: macOS 14.6.1, arm64 (Apple Silicon), Python 3.14.7, pytest 9.1.1; environment was newly prepared via existing `uv` and repository `uv.lock`.
- **Isolation**: independent test checkout and isolated HOME; `sandbox-exec` profile `(version 1)(allow default)(deny network*)`. This is network isolation, **not** a general filesystem write denial. No live AI-provider requests were made.
- **Runner**: `bash scripts/run_tests.sh -j 2 --file-retries 0 --tb=short` against the *same 25 changed Python test files* enumerated by the original package.
- **Mac outcome**: **289 tests passed, 0 failed, 0 skipped; exit code 0; elapsed 32.0 seconds**. Exact HEAD/tree stable and `git status --porcelain -uno` clean before/after.
- **Previously Linux-skipped 2 tests**: `tests/gateway/test_proxy_mode.py` `@pytest.mark.platforms("macos")` cases now ran as part of all-25 suite. A separate focused execution of that test file yielded **19 passed, 0 failed; exit 0**.
- **Linux comparison** (previous independently executed): 287 passed / 0 failed / 2 skipped, exact same code HEAD/tree.

## Evidence verification

| Receipt | Original Mac SHA-256 | Public redacted SHA-256 |
| --- | --- | --- |
| Full 25-file Mac run | `c8123157b08147bd3053d36b04337f6c5cdd2690cdd679cd87b71d514705204a` | `d45002c0861e2feaab0e49f0bae0935d7bb23be9d15ea86e37330861492d8538` |
| Focused Mac proxy file | `f1871d03bd15f6a1ccaeabbca8ab5ed353f1063e896e95ac9cf060e51cabd284` | `14e3167808a77cc0867f3662176058cf0bc21475cea82ae72a193c17ed894e35` |

The logs were copied from Mac through J1 onto the reviewer workstation, and **the original SHA-256 values were verified identical** on both machines. Only the redacted copies are published. See `manifest.json` for per-file hashes.

## Verification boundary

This is independent **local Mac execution evidence**, **not** an upstream exact-head hosted GitHub Actions green check. The whole Hermes repository suite and live-provider integration were not exercised. Original COMMENT review remains unchanged. No claim is made that CI/Docker/Nix are currently green.
