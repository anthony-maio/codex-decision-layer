---
name: evidence-selection
description: Compare passage relevance with Jev or a local Eve decision model, preserve the original evidence, and inspect uncertain decisions. Use when the user asks to use Decision Layer, evaluate retrieved passages, or compare the decision backends.
---

# Evidence selection

Use the plugin's `shadow_evidence` tool with the user's question and explicitly chosen files under the configured root. The tool returns every passage, a stable source reference, and the proposed relevance decision. Read the source evidence when answering; the decision is a diagnostic signal.

Use `read_evidence` to expand surrounding lines when a passage is incomplete or a decision looks questionable. Keep contradictions and uncertainty visible. Do not interpret a relevance score as truth, authorization, or task completion.

The initial Eve checkpoint retained every passage in the small relevance fixture. Jev filtered more selectively. Treat model suitability as an open evaluation question. Do not claim a speedup or token saving from proposed byte reduction.

Configuration lives in `~/.codex/decision-layer.json`, or the file selected by `DECISION_LAYER_CONFIG`. The configured provider determines whether passage text stays local or goes to TypeSafe/OpenRouter. Never read or submit `.env` files, private keys, or credential stores as evidence.

If configuration is missing, use the repository's `evidence-selector configure --root PATH` command with the intended provider. A local model server must be running before using the Eve provider. An unavailable model retains evidence and records an error; this is not successful inference.

This plugin adds explicit tools. It does not intercept Codex's built-in tool calls, alter approvals, or compact history.
