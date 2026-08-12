---
name: codex-cost-optimizer
description: Use when starting or changing phases of Codex work where model/reasoning choice affects cost, including spawned subagents when their runtime configuration is observable.
---

# Codex Cost Optimizer

## Overview

Use the local `cco` router before expensive Codex work whenever the current model may be oversized or undersized. The router follows a **zero-token-first** policy: deterministic local rules decide whenever confidence is sufficient; bounded AI classification is fallback only for materially ambiguous work.

## Mandatory Rules

- Never change `model` or `reasoning_effort` without **autorização explícita** do usuário.
- Present **uma recomendação** only, with current configuration, target configuration, concrete reason, and expected cost direction.
- Silence is denial. A rejected switch stays suppressed until the phase fingerprint changes.
- Use only models returned by the current Codex runtime catalog. Never assume Spark or any other model is available.
- Prefer the cheapest configuration with enough capability; when uncertainty creates meaningful retrabalho risk, prefer the safer capable model.
- Re-evaluate only on an objective phase change, new evidence, relevant error, scope change, or subagent spawn.
- Never edit the user's **configuração global** for temporary routing. Keep changes scoped to the owned thread/turn.
- If state, catalog, or switch confirmation is unavailable, fail safe: keep the current/inherited configuration and continue normal Codex work.
- Never persist source code, full prompts, responses, secrets, or repository contents in telemetry.

## Workflow

1. Run `cco inspect` to discover the real catalog when entering a new environment.
2. Route the next phase with local metadata before the work turn.
3. If a switch is material, show one approval request and wait for explicit consent.
4. Apply only the approved `model + reasoning` pair and validate it against advertised efforts.
5. Record metadata/usage locally; label parent-model comparisons as estimated counterfactuals.
6. For subagents, apply the same policy only when the runtime exposes independent routing safely; otherwise inherit the parent and record the limitation.

## Cost Guard

AI fallback is allowed only for low-confidence, materially valuable decisions. Keep classifier payload metadata-only, at or below 1,000 estimated input tokens and 80 output tokens. Target >90% local routing and <1% optimizer overhead on representative sessions.
