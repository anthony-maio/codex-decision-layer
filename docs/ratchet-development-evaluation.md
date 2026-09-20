# Development experiment 1

Declared before hosted Ratchet calls. This document does not freeze a holdout.

Use the reviewed authored development corpus only. Compare exact matching, an
additional deterministic explicit-exception-chain matcher, and that stronger
matcher plus Jev 1.13.0 for unresolved, complete single-failure pairs. Independent
review identified the stronger baseline before any hosted development calls.
The initial prompt and three choice criteria are in `ratchet/semantic.py`.
Only stage and complete failure text are submitted. Oversized input abstains
without truncation. Task metadata, labels, retry-intent annotations, and raw
auxiliary stdout are excluded. Hosted evidence upload is explicit.

Make at most one provider call per unresolved case, with no retries. Initial
choice probability threshold is 0.8. Examine thresholds 0.6, 0.7, 0.8, and 0.9
using the same recorded distributions, never new calls for threshold exploration.
Choose the highest threshold meeting the predeclared development quality gates;
if none passes, report that before changing the prompt or corpus. The provider's
confidence field is retained separately and is not a calibrated correctness rate.
Limit this first experiment to 30 requests and preserve any failed-call receipts.

Record exact corpus and implementation hashes, decision probabilities, provider
model identity, input/output usage, selector latency and errors. Do not infer
whole-task savings from these pair classifications. The initial corpus has only
two attempts per case, so all cases are ineligible for advisories; a separately
reviewed sequence corpus is required for the advisory gate.

The authored corpus is a controlled feasibility test, not evidence of performance
on public repositories or naturally occurring agent sessions. Those claims need
their own labeled cases and results. Independent label review is not human
ground truth. Freeze a separate holdout only after development changes finish.
