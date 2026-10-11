# Security and release criteria

**Status: early alpha / experimental.** This tool verifies PR *metadata consistency*, not code safety.

A `SNAPSHOT_MATCH_ONLY` or `RECORDED_GATES_MATCH_UNTRUSTED` result is **not approval** to publish, merge, or run arbitrary shell commands. Logs from an agent are untrusted even if they look green.

For a complete review process, separately establish:
1. Exact GitHub HEAD, branch/source identity and changed-file diff;
2. CI result from GitHub/another trusted executor;
3. Test commands and exit codes in an isolated, credential-free environment;
4. Independent reviewer identity and review scope;
5. Explicit human approval for public mutation.

Never expose personal memory, cloud service tokens, GH auth stores or open network access to a process evaluating untrusted PR code.

**Limitations:** GitHub CLI auth scope is as configured on the user's host; running a read-only command does not restrict what other software using that token could do. Hermes `status.json` and `acceptance.json` remain self-attestations. The tool does not verify signatures or CI provenance. If malicious code controls the Python interpreter or local filesystem, this tool cannot guarantee trust.

Please report privately to the repository owner before public disclosure of credential or approval bypass vulnerabilities.
