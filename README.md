# PR Evidence Gate

**Read-only, fail-closed PR verification for contributors and maintainers — v0.2.0.** Lightweight Python CLI. Reuses GitHub CLI (`gh`), local Git, and *optional* existing Hermes Loop artifacts. Does not invent another agent orchestration layer, task database, or PR reviewer.

**繁體中文**：PR 證據閘門是一個輕量開源工具，核對 GitHub PR HEAD、本地 Git 工作樹，以及可選的 Hermes 驗收紀錄。適用於維護者與貢獻者兩種工作流程。**所有結果都不代表授權 Push、Merge、核准或公開發布**。

## Install and diagnose (v0.2.0)

See [the step-by-step installation guide](docs/INSTALL.md) for
macOS/Linux, Windows PowerShell, and first-time GitHub CLI setup.

```bash
git clone https://github.com/j0935586110-lgtm/pr-evidence-gate.git
cd pr-evidence-gate
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
pr-evidence-gate doctor
```

`doctor` returns structured JSON and actionable commands if Git, GitHub CLI
or GitHub authentication is missing. A real PR check still requires a local
checkout of that PR and separate verification of trusted CI.

## Requirements

- Python **3.10+**
- Git CLI and [GitHub CLI](https://cli.github.com/) (`gh auth login`)
- A **local checkout** of the PR you intend to check
- Optional: an existing [Hermes Loop](https://github.com/NousResearch/hermes-agent) automation run with `.hermes/status.json` and `.hermes/acceptance.json` in the checkout

## Quick start

```bash
git clone https://github.com/j0935586110-lgtm/pr-evidence-gate.git
cd pr-evidence-gate
python3 -m unittest discover -s tests -v
python3 tools/pr_workflow.py doctor

# Maintainer: exact remote HEAD and local worktree check
python3 tools/pr_workflow.py --mode maintainer \
  --repo NousResearch/hermes-agent --pr 99053 \
  --worktree /path/to/checked-out-pr

# Contributor: also checks existing Hermes run status/acceptance artifacts
python3 tools/pr_workflow.py --mode contributor \
  --repo NousResearch/hermes-agent --pr 99053 \
  --worktree /path/to/checked-out-pr
```

CLI: `pr-evidence-gate check --mode maintainer ...` is equivalent to the
legacy `python3 tools/pr_workflow.py --mode maintainer ...` form.
`pr-evidence-gate doctor --worktree PATH` inspects prerequisites without
attempting to check a remote PR.

Command exit codes: **0** = snapshot consistency only (never publication approval); **2** = blocked by a gate; **3** = I/O/tool/other error. JSON output is suitable for a CI report or Agent handoff.

## What it does

| Mode | Checks | Does not do |
|---|---|---|
| **Maintainer** | GitHub PR open status, exact remote SHA, local SHA, clean worktree | Merge, review, comment, create branches |
| **Contributor** | Above, plus *existing* Hermes status, acceptance gates, review SHA, and local evidence paths | Run untrusted test commands; trust an AI's self-reported approval |

This is an **independent consistency filter, not an independent test runner**. Local agent-produced logs may be forged. Verify CI jobs, actual test commands, provenance, review authenticity and authorization separately.

## Security boundary

- Read-only external `gh pr view`; read-only Git queries; no write mutation or public action.
- Input values go into fixed subprocess argument arrays, not shell strings.
- Secrets are not printed to error messages.
- JSON evidence read is bounded to **1 MiB** through a regular, non-symlink file descriptor.
- Dirty/unknown state, stale HEAD, missing Hermes evidence: fail closed.
- **Do not run AI-generated tests or third-party PR code without OS-level sandboxing.**
- A DSH `read-only` permission preset is **not** a home-directory or network access boundary.
- Deployment of a tool into a privileged Agent context remains the operator's responsibility.

For the isolation research, see [Security notes](docs/SECURITY.md). Full private session logs, provider credentials and internal machine paths are intentionally excluded from this public repository.

## Integrate with existing agents

Use this CLI as a guard before an existing Hermes / DSH / OpenCode / CI transition. It deliberately does not manage agent queues, send API tokens to models, or deploy anything. GitHub remains the source of truth for PR HEAD, Hermes remains the source for its own workflow state.

Run checks after new commits and before preparing release evidence; **always independently inspect GitHub Actions, CI status and changed files**. A successful snapshot does not make a PR safe.

## License

**Apache License 2.0** for v0.2.0 and subsequent releases. See
[LICENSE](LICENSE) and [NOTICE](NOTICE). The original v0.1.0 release
was MIT-licensed and remains available under its historical terms.

Issues and small reproducible PRs welcome.
