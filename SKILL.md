---
name: codex-cost-optimizer
description: Use when starting or changing phases of Codex work where model/reasoning choice affects cost, including spawned subagents when their runtime configuration is observable.
---

# Codex Cost Optimizer

## Overview

Use the local `cco` router before expensive Codex work whenever the current model may be oversized or undersized. Follow a **zero-token-first** policy: prefer deterministic local routing; use bounded AI classification only for materially ambiguous work.

## Mandatory Rules

- Never change `model` or `reasoning_effort` without **autorização explícita** do usuário.
- Present **uma recomendação** only, with current configuration, target configuration, concrete reason, and expected cost direction.
- Silence is denial. A rejected switch stays suppressed until the phase fingerprint changes.
- Use only models returned by the current Codex runtime catalog.
- Prefer the cheapest configuration with enough capability; when uncertainty creates meaningful retrabalho risk, prefer the safer capable model.
- Never edit the user's **configuração global** for temporary routing.
- Never persist source code, full prompts, responses, secrets, or repository contents in telemetry.

## Main Thread

For the main Codex thread opened in VS Code:

1. Evaluate the current `model + reasoning` before expensive work.
2. If a material change is recommended, explain the current pair, target pair, concrete reason, and cost direction.
3. Ask for explicit user authorization.
4. If authorized, tell the user to change the pair in the **seletor nativo** do Codex.
5. **Não tente alterar automaticamente a thread principal** through `config.toml`, private databases, UI automation, or undocumented APIs.
6. Confirm the effective state when the runtime exposes it before treating the switch as complete.
7. Only then continue the expensive phase.

## Subagente / Subagents

Subagents can be configured when spawned:

1. Re-evaluate each subagent task independently instead of inheriting the parent model by default.
2. Present one approval decision for the planned subagent configuration or batch.
3. After explicit authorization, pass the selected `model` and `reasoning` **explicitamente** to the subagent spawn/dispatch operation.
4. If independent routing is not supported or cannot be confirmed, inherit the parent configuration and record that limitation.
5. Record plugin/Skill origin, agent name/ID, parent model/reasoning, actual model/reasoning and usage when observable. Parent-model savings remain estimated counterfactuals.

## Cost Guard

AI fallback is allowed only for low-confidence, materially valuable decisions. Keep classifier payload metadata-only, at or below 1,000 estimated input tokens and 80 output tokens. Target >90% local routing and <1% optimizer overhead on representative sessions.
