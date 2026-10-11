# Install and first PR check

PR Evidence Gate 0.2.0 supports a low-dependency Python CLI, not yet a
double-click GUI app. Downloading the source lets you **run unit tests**
immediately with Python, but checking a real PR requires Git and GitHub CLI.

## Prerequisites

- Python 3.10 or newer, Git, and [GitHub CLI (gh)](https://cli.github.com/)
- Run `gh auth login --hostname github.com` (or use an appropriately scoped CI token)
- A local working copy of the **specific PR HEAD** to check
- Optional: Hermes run's `.hermes/status.json` and `.hermes/acceptance.json`
  to use Contributor mode. Hermes is **not** required for Maintainer mode.

## 1. Install

### macOS / Linux

```bash
git clone https://github.com/j0935586110-lgtm/pr-evidence-gate.git
cd pr-evidence-gate
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
pr-evidence-gate --version
pr-evidence-gate doctor
```

### Windows PowerShell

```powershell
git clone https://github.com/j0935586110-lgtm/pr-evidence-gate.git
cd pr-evidence-gate
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\pr-evidence-gate.exe --version
.\.venv\Scripts\pr-evidence-gate.exe doctor
```

If virtual environments are inconvenient, run directly from source instead:
`python3 tools/pr_workflow.py doctor` (or `py -3 tools/pr_workflow.py doctor`).

`doctor` checks installed executables and GitHub login. Missing prerequisites
return a **BLOCKED** JSON with installation commands; it does not install or
authenticate anything automatically.

## 2. Check a PR

Use a separate checkout/worktree for a target PR. The tool deliberately
does **not** clone, fetch, or execute PR code, nor does it automatically
mutate your existing checkout.

```bash
pr-evidence-gate doctor --mode maintainer --worktree /path/to/pr-checkout
pr-evidence-gate check --mode maintainer \
  --repo OWNER/REPO --pr 123 --worktree /path/to/pr-checkout
```

For a Hermes-based contributor run, use `--mode contributor` and point to
the checkout containing its existing Hermes evidence files.

On PowerShell, put the command on one line or use PowerShell backticks
instead of the Unix-style trailing backslashes.

## Interpret results

- Doctor exit **0**: runtime prerequisites ready for **metadata checking**;
  it is **not** a PR success or approval.
- Check exit **0**: PR identity + local metadata match; **not** publication approval.
- Exit **2**: fail-closed blocked by missing prerequisites/evidence.
- Exit **3**: tool runtime/error; cannot claim verification.

The tool doesn't verify CI independently or approve merging. Do that in a
separate trusted workflow. Never execute third-party PR code on a host
containing production credentials.

## License versions

**v0.2.0 onward: Apache-2.0.** Original `v0.1.0` was released under
MIT; its original tag and historical rights remain intact.
