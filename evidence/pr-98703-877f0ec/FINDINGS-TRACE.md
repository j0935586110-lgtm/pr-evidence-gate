# Line-level review trace for current head 877f0ecbf1

All code references here target exact PR commit 877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645. They are **static source observations** unless paired with local executed receipts. For the local code health before/after, see `logs/code-health-before.log` vs `logs/code-health-current-health-only.log`.

## Five BLE001 findings and FILE_LINES

The before health log lists five BLE001 finding locations: `gateway/run_turn_routing.py:123,133`; `hermes_cli/cli_agent_setup_mixin.py:39,673`; `hermes_cli/cli_commands_mixin.py:548`. The current full and matched health-only logs report no blocking findings. This establishes the linter outcome; it is not a proof of exception handling semantics. Source inspection found `logger.warning(..., exc_info=True)` at `gateway/run_turn_routing.py:123-124` and `logger.debug(..., exc_info=True)` at `gateway/run_turn_routing.py:133-134`. Both expose traceback information to logging (at different logging levels); runtime handling is separate from the linter result.

Of the original **six FILE_LINES** blockers, **two are addressed by topical extraction** into `hermes_cli/plugin_command_dispatch.py`, `tests/hermes_cli/test_plugins_turn_routing.py` and `tests/hermes_cli/test_plugin_command_dispatch.py`; the remaining **four** use local ratchet-sanctioned header waivers at `gateway/run_inbound.py:1`, `gateway/run_turn.py:1`, `gateway/run_turn_runner.py:1`, and `hermes_cli/cli_commands_mixin.py:1`. A waiver that makes the script pass is not automatically a maintainer's approval of design.

## Image selection and runtime binding

- [Quiet CLI helper](https://github.com/NousResearch/hermes-agent/blob/877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645/hermes_cli/cli_single_query.py#L348-L402): `scoped_runtime_main` wraps `_preprocess_images_with_vision` (around lines 383-387), so route-selected runtime is visible during auxiliary analysis.
- [Production quiet caller](https://github.com/NousResearch/hermes-agent/blob/877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645/hermes_cli/cli_single_query.py#L551-L563): calls `cli._resolve_turn_agent_config(query)` before passing the concrete `turn_route` to the image helper.
- [Selected-route resolver](https://github.com/NousResearch/hermes-agent/blob/877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645/hermes_cli/cli_agent_setup_mixin.py#L608-L672): starts with `_current_runtime(self)` and re-resolves credentials when routing changes.
- [Interactive counterpart](https://github.com/NousResearch/hermes-agent/blob/877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645/hermes_cli/cli_chat_turn_mixin.py#L229-L235): scopes text fallback at the realized route.
- [New quiet regression](https://github.com/NousResearch/hermes-agent/blob/877f0ecbf1159a2ee5ddbe6577f4fd1e19b87645/tests/hermes_cli/test_cli_image_command.py#L157-L200): exercises thrown exception, inner-scope unwind and outer-scope restoration; the canonical focused 9-test file run is in `logs/exact-head-provenance-9tests.log`.

These source ranges can be rechecked against exact GitHub code; no assertion is made that a production provider was contacted. The independent full Linux suite tested 25 affected test files, not the entire project. No new P1/P2 from the AGY hypotheses survived checking the real production caller; other untested paths remain possible.
