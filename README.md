# Codex Cost Optimizer

Local, approval-gated Codex model/reasoning router focused on reducing credit/token spend without materially increasing rework risk.

## V1 behavior

- Dynamic model catalog from the official `openai-codex` SDK.
- Zero-token local classification first; bounded AI fallback only for materially ambiguous work.
- Explicit authorization for every model/reasoning change.
- **Main thread:** recommendation + authorization + manual change in the native Codex model selector. No private VS Code integration and no global `config.toml` mutation.
- **Subagents:** after authorization, the selected `model + reasoning` can be passed explicitly at spawn/dispatch time when the runtime supports independent routing.
- Privacy-safe JSONL telemetry outside the project.
- Versioned pricing and estimated parent-model counterfactual savings.

## Install

```bash
python -m pip install -e ".[codex,dev]"
```

## Commands

```bash
cco inspect
cco inspect --thread-id <thread-id>
cco run "Adicione XML comments" --model gpt-5.6-sol --effort high --files 1 --risk low
cco report <session-id>
```

When `cco run` determines that the main thread should use another configuration and the user authorizes it, the command returns a `manual_switch_required` instruction instead of executing the work turn with an automatic override.

```text
manual_switch_required=true
target_model=gpt-5.3-codex-spark
target_effort=low
action=altere model/reasoning no seletor nativo do Codex e confirme o estado antes de continuar
```

## Capability boundary

- no VS Code extension is required;
- transparent mutation of the main VS Code thread is not claimed;
- the native model selector is used for the main thread;
- pre-spawn routing is supported for subagents through explicit configuration returned by the router;
- global Codex configuration is never changed as a temporary routing mechanism.

## Privacy

Telemetry stores metadata only. It rejects unknown fields and never stores prompt text or source files.

- Windows: `%LOCALAPPDATA%/codex-cost-optimizer/telemetry/events.jsonl`
- Linux/macOS: `${XDG_STATE_HOME:-~/.local/state}/codex-cost-optimizer/events.jsonl`
