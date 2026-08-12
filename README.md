# Codex Cost Optimizer

V1 core for a local, approval-gated Codex model/reasoning router focused on reducing credit/token spend without materially increasing rework risk.

## What is implemented

- Dynamic model catalog from the official `openai-codex` SDK.
- Zero-token local signal extraction and deterministic classification.
- Cost/capability routing against models actually available to the account.
- Explicit authorization for every model/reasoning change.
- Anti-oscillation after denial and materiality gate for tiny savings.
- Per-turn runtime override; no temporary changes to global `config.toml`.
- Privacy-safe JSONL telemetry outside the project.
- Versioned pricing and explicitly estimated parent-model counterfactual savings.
- Optional metadata-only AI fallback capped at ~1,000 input / 80 output tokens.
- `SKILL.md` policy for use in Codex/agent runtimes.

## Install

```bash
python -m pip install -e '.[codex,dev]'
```

The official Python SDK requires Python 3.10+ and reuses an existing Codex authentication session when available.

## Commands

```bash
cco inspect
cco inspect --thread-id <thread-id>
cco run "Adicione XML comments" --model gpt-5.6-sol --effort high --files 1 --risk low
cco report <session-id>
```

For the Core CLI, a new thread needs explicit `--model` and `--effort` so the router knows the starting configuration before the first work turn. The planned VS Code companion supplies this state automatically.

## Privacy

Telemetry stores metadata only. It rejects unknown fields and never stores prompt text or source files. Default locations:

- Windows: `%LOCALAPPDATA%/codex-cost-optimizer/telemetry/events.jsonl`
- Linux/macOS: `${XDG_STATE_HOME:-~/.local/state}/codex-cost-optimizer/events.jsonl`

## Current V1 boundary

The Core does not claim transparent interception of the official VS Code Codex composer or arbitrary plugin subagent spawns. Those are separate adapter plans and must capability-check the runtime before enabling automatic routing.
