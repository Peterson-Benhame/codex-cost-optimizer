# Core V1 — Verification Status

## Verified in the build sandbox

- Full pytest suite passes.
- Python sources compile with `compileall`.
- Editable install works offline with local build dependencies (`--no-build-isolation`).
- `cco --help` exposes `inspect`, `run`, and `report`.
- Dynamic catalog mapping is tested with runtime-shaped fakes.
- Unsupported `model + reasoning` pairs are rejected before the owned turn call.
- Trivial work on an expensive model produces one economical recommendation.
- Explicit denial keeps the current configuration and suppresses the same recommendation for that phase fingerprint.
- Authorized configuration failure falls back to current configuration without global config edits.
- AI fallback is metadata-only, conditional, and tested against the 1,000 input / 80 output budget contract.
- Optimizer can be disabled and then performs no recommendation or switch.
- Telemetry schema rejects prompt/source fields and separates measured tokens from rate-card cost estimates.

## Live gate still required on the user's machine

The sandbox does not have the user's Codex authentication/session. Before starting the VS Code integration plan, run:

```bash
python -m pip install -e '.[codex,dev]'
cco inspect
```

Expected live evidence:

1. `cco inspect` returns the account's real model catalog.
2. GPT-5.3-Codex-Spark appears only if the account/runtime returns it.
3. Each displayed model lists only reasoning efforts advertised by the runtime.

No model work turn is required for this catalog-only gate.
