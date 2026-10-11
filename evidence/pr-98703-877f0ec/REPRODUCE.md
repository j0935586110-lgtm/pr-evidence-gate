# Reproduce locally (read-only with respect to upstream GitHub)

These commands create or change a **disposable test checkout only**, not any public GitHub state. First install Python 3.14.7 and project dependencies from `uv.lock` in a networked **preparation** environment. Execute tests afterwards inside a container with networking disabled, no production credentials, a read-only source mount, isolated writable tmpfs, and pinned dependencies. The shell blocks below show the commands run **inside that confined environment**, not an invitation to execute untrusted PR code directly on a production host.

```bash
git clone https://github.com/NousResearch/hermes-agent.git /tmp/hermes-pr98703-check
cd /tmp/hermes-pr98703-check
git fetch origin pull/98703/head
git checkout --detach 877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645
test "$(git rev-parse HEAD)" = "877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645"
git status --porcelain
```

## Current head source health

```bash
python3.14 scripts/check
# Independent receipt at HEAD: exit 0, 11 checks ok, 0 blocking.
```

## Changed test files

```bash
# The 25-file selection lives alongside this note as tests/changed-test-files.txt.
# Read it into a Bash array; do not assume test suites dynamically discover exactly these files.
mapfile -t test_files < /path/to/unzipped-bundle/tests/changed-test-files.txt
bash scripts/run_tests.sh -j 2 --file-retries 0 --tb=short "${test_files[@]}"
# Linux independent receipt: 287 passed, 0 failed, 2 skipped.
```

## Before/after code-health comparison

On a distinct expendable checkout of the earlier commit (or `git worktree`, outside any production checkout):

```bash
git fetch origin pull/98703/head
# Note: an older pre-fix object may be unavailable after a force-push.
git checkout --detach 14f49cbfa3d4ca55a7ee13031724a1d9416f8466
python3.14 scripts/check --only health
# Independent local receipt: exit 1, 11 blocking.
```

Both before and after **health-only** receipts used the same merge-base `302c5d9f679333ae957c256d76a3dff35120f4e0`. The separately run full `python scripts/check` succeeded at head. Code-health numbers can change if the ratchet's main reference moves; pin the comparison for an exact replay. See `logs/code-health-current-health-only.log` for the like-for-like outcome.

## Contributor email workflow

Read the actual `.github/workflows/contributor-check.yml`. Its logic takes `MERGE_BASE=$(git merge-base origin/main HEAD)`, the non-merge author email set from `git log MERGE_BASE..HEAD --format='%ae' --no-merges | sort -u`, and tests mappings against `contributors/emails/` or the frozen `scripts/releases/authors_legacy.py`. Run this in an isolated checkout with an appropriate pinned main ref. The DSH receipt uses the **GitHub-provided** `refs/pull/98703/merge` commit `48a375f33aabf8fe901fa1ff0a66f5fbfffdc5df`, verified directly through GitHub REST ref lookup on 2026-10-11. Its main parent is `0faf0938ebdc4420e11070822cf4f9db09eb4260`, head parent is `877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645`. The pre-fix branch checkout has a different commit range (including unrelated upstream authors). A local replay PASS is not a hosted Action. To refresh a moving PR merge ref, `git fetch origin pull/98703/merge`; compare SHA before reusing these receipts.

## Independent evidence integrity

```bash
python3 - <<'PYV'
import hashlib, json
from pathlib import Path
manifest = json.loads(Path('manifest.json').read_text())
for item in manifest['files']:
    raw = Path(item['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item['sha256'], item['path']
print('PUBLIC_PACKAGE_HASHES_OK')
PYV
```
