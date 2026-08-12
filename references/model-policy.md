# Model Policy

The runtime catalog is the source of truth for availability and supported reasoning efforts. `model-policy.json` only enriches known model IDs with relative capability, relative cost, preferred phases, and versioned pricing metadata.

Routing phases:

- `mechanical`: low-cost model, low reasoning.
- `defined_implementation`: economical/intermediate model, medium reasoning.
- `complex_engineering`: strong model, no more reasoning than needed.
- `investigation`: strongest justified model, typically high reasoning.

Low-confidence classification adds one capability tier of safety margin. Unknown models remain visible but are not automatically ranked until policy metadata exists. Exact prices older than 30 days are marked stale; routing then relies on relative cost rank instead of claiming exact savings.

Pricing source recorded in V1: OpenAI Codex rate card. GPT-5.3-Codex-Spark is intentionally marked research preview and has no invented numeric price.
