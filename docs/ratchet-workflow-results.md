# Ratchet repair workflow: results and limits

Status: all 45 assigned workers completed. Usefulness gates failed. [Independent aggregate review](../results/ratchet/workflow-final-review.json) passed with no remaining findings; this is not human validation.

This experiment does not establish an original confirmatory usefulness result. The first two Ratchet workers missed their required MCP calls, and subsequent runs used a disclosed startup amendment. One Jev-assisted invoice repair also failed an independent grading test. Every attempt remains in its original assigned position; no worker was replaced or given a corrective prompt.

## Results from every assigned run

Each row includes all five assigned runs. Costs are selector-inclusive API-equivalent median estimates in US dollars. Unknown means at least one assigned run lacks complete accounting; it is not a zero cost.

| Task | Method | Quality passes | Method passes | Median seconds | Median cost |
| --- | --- | ---: | ---: | ---: | ---: |
| Invoice | Plain Codex | 5/5 | 2/5 | 54.399 | $0.143979 |
| Invoice | Deterministic Ratchet | 5/5 | 4/5 | 85.478 | Unknown |
| Invoice | Ratchet plus Jev | 4/5 | 4/5 | 71.002 | Unknown |
| Queue | Plain Codex | 5/5 | 1/5 | 46.866 | $0.171305 |
| Queue | Deterministic Ratchet | 5/5 | 5/5 | 55.550 | $0.216736 |
| Queue | Ratchet plus Jev | 5/5 | 5/5 | 61.297 | $0.206622 |
| Events | Plain Codex | 5/5 | 1/5 | 43.762 | $0.137664 |
| Events | Deterministic Ratchet | 5/5 | 5/5 | 62.069 | $0.240350 |
| Events | Ratchet plus Jev | 5/5 | 5/5 | 57.293 | $0.214841 |

The geometric mean of per-task median latency ratios was 1.382 for deterministic Ratchet versus plain Codex, 1.307 for Ratchet plus Jev versus plain Codex, and 0.946 for Jev versus deterministic Ratchet. All three usefulness comparisons failed. Jev's smaller time relative to deterministic Ratchet does not pass the declared performance gate, and its invoice quality regression fails the quality gate. Unknown invoice costs prevent aggregate cost gates from being established. No savings or anti-thrashing benefit is demonstrated.

There were 44 quality passes and 32 method passes across 45 assigned runs. The 13 method failures consist of two missed MCP integrations and 11 plain workers whose batched output failed the frozen reader verifier. The supplementary audit found both complete originals in all 11 plain-worker outputs. Those observations explain the verifier limitation without changing any assigned outcome or gate.

Worker time totaled 2,752.724 seconds, with no timeout penalties. Separate grading took 17.877 seconds. Reported worker usage was 8,342,692 input tokens, including 7,360,512 cached input tokens (88.23%), and 97,982 output tokens, including 24,587 reasoning tokens. The 43 runs with complete full-task cost bounds sum to $8.496470-$9.149023; the other two costs remain unknown, so this is not a total experiment cost. Per-method cache fractions and all underlying bounds are in the [descriptive summary](../results/ratchet/workflow-summary.json).

Observed selector work included 135 tool calls taking 5.996 seconds, including nine Jev requests taking 4.770 seconds, 11,013 input tokens, and 477 output tokens. The observed Jev cost estimate was $0.000463. These observations are incomplete for the two original integration failures. Complete accounting on the other 43 runs recorded no provider errors or retries. No worker retry notices appeared; the CLI does not expose an authoritative retry count. There were 52 observed test commands and no repeated completed command strings, which does not establish absence of semantic repetition.

## What the real comparisons returned

The [decision audit](../results/ratchet/workflow-decisions.json) binds the 28 observed MCP comparisons to the original event hashes and frozen record hashes. Four invoice Jev calls returned `same_blocker`; their deterministic counterparts abstained. Five event Jev calls abstained because confidence did not meet the frozen threshold, as did their deterministic counterparts. All ten queue comparisons identified execution advancing to a different blocker without a provider request. The first two assigned Ratchet workers had no observed comparison.

This demonstrates that Codex can record failures, request a semantic comparison, retrieve the originals, edit code, and run tests. Three of the four invoice workers that received a semantic `same_blocker` result passed all grading tests; slot 36 did not. These are descriptive integration observations from the full experiment, not a selected subset that establishes usefulness.

## What was measured

The frozen schedule assigns five matched triplets to each of three authored Python repairs: invoice arithmetic, ready-job ordering after a setup fix, and event replay after a sequence-gap fix. Each triplet compares plain Codex, deterministic Ratchet, and deterministic plus Jev. Workers receive the same contracts, current source, visible tests, and two historical failure records. They must edit the implementation and run the supplied test command. Separate frozen graders check the final source in a fresh workspace.

The experiment uses native Linux, Codex CLI 0.146.0, gpt-5.6-sol with low reasoning, and normal workspace-write permissions. Windows has separate real repair and installation checks; these timings do not describe Windows agent performance. The hosted model is an alias. Its weights, service load, and cache behavior are not frozen by pinning the CLI.

The full worker timer includes process startup, MCP startup, tool calls, edits, test execution, and owned-process cleanup. Selector timings include local transport and metering overhead. They are part of full-task time, not an amount to subtract from it. Independent grading occurs afterward and is reported separately. Recorded command repetition is descriptive; equal command text does not establish wasted work.

## Method failures and the startup amendment

The first triplet used the original optional-server setup. Its two Ratchet workers completed their repairs without the assigned MCP calls. Their method failures and unknown selector-inclusive costs are preserved. Four separate unscored startup diagnostics led to an amendment requiring the experimental MCP server from slot 3 onward. No original worker was replaced. That change can abort a worker if server startup fails; the product plugin still uses an optional server and deterministic shadow mode by default.

The frozen plain-mode verifier expects the supplied reader's entire command output to be JSON. Workers sometimes batched that reader with other inspections. The supplementary observation audit checks complete payload bytes against original hashes bound to the workflow freeze, even when the payload is one line within a larger output. It records observed evidence separately and never changes method flags, cost accounting, or gates. See the [amendment](ratchet-workflow-amendment-1.md) and [observation audit](../results/ratchet/workflow-observation-notes.json).

## Independent grading failure

Slot 36, an invoice repair assigned to the Jev method, passed its visible test but passed only 38 of 39 independent grading tests. With no line items and `shipping_cents=10**60`, its Decimal calculation raised `decimal.InvalidOperation` instead of returning the shipping amount. The contract permits a nonnegative integer without an upper bound. The supplied tests, records, and contract were unchanged; this is a retained repair failure, not a modified grading criterion.

This observation does not establish that Jev caused the mistake. It does count against the predeclared task-quality gate. A successful visible test or plausible final answer cannot replace independent grading.

## Accounting and interpretation

Costs are API-equivalent estimates at the protocol's frozen rates, not Codex subscription bills. They include reported cache reads and writes and known Jev usage. Aggregate worker input cannot establish individual request sizes, so possible long-context surcharges remain bounds. A missing full-task cost prevents that group's median cost and comparative cost gate from being established. Observed subtotals are labeled as incomplete rather than presented as complete totals.

Exact model transport retry counts are unavailable from this CLI. JSON retry notices and stderr retry notices are separate observations and may describe the same event. Provider retries, errors, tokens, and latency are reported where selector accounting is complete. A partial meter retains observations without turning them into complete totals. Interrupted runs remain assigned failures; any declared latency penalty is distinguished from measured elapsed time.

Historical-record preparation and unscored integration/startup diagnostics are outside the task timer and have separate receipts. The four startup diagnostics used 142.672 seconds of worker time and an API-equivalent worker estimate of $0.5987144. These are setup costs, not savings. Package-installation elapsed time was not measured; installation receipts identify the wheel and dependency constraints.

The tasks are small authored examples, with five runs per method and task. Their contracts and tests make failures reproducible, but do not establish performance on large repositories or naturally occurring debugging loops. The event task explicitly stresses the previously observed terminal-callback weakness; it is not a new classification holdout. No classifier or prompt was tuned during the experiment.

## Reproduction and release behavior

Use the [frozen protocol](ratchet-workflow-protocol.md), [reproduction instructions](ratchet-workflow-reproduction.md), and the separate amendment. Later packaging changes do not replace the first committed experiment inputs. Raw sessions, local record paths, credentials, and machine-specific handoffs remain outside Git.

The numeric summary can be reproduced from the published receipt without credentials or model calls. Run this from the release checkout, using a new output filename:

```sh
uv run --no-sync python scripts/summarize_ratchet_workflow.py --receipt results/ratchet/workflow-v1.json --output ../workflow-summary-reproduced.json
```

The decision and observation audits additionally require the private event logs and original records from the corresponding run. Their published hashes permit identity checks; the public release does not contain those raw sessions. A fresh reproduction creates its own evidence and cannot reproduce the original hosted responses exactly.

Classification had already failed its precision and critical-case gates. The completed workflow also failed usefulness. Ratchet remains experimental and shadow-only. Advisory behavior and filtering are disabled. Original reports remain recoverable, and a comparison failure leaves ordinary investigation available.
