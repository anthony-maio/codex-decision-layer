# Ratchet prospective repair workflow protocol

Status: DRAFT, not frozen and no scored worker runs yet.

This experiment asks whether explicitly consulting Ratchet helps Codex complete
an actual repair. Each worker reads an authored Python project and two recorded
failed attempts, edits its implementation, and runs tests. Classification replay
and answers about what someone should edit do not count as a completed repair.
The tasks are small authored examples. Results cannot establish performance on
large repositories or naturally occurring agent loops.

## Inputs and methods

Use three tasks: invoice arithmetic after an ineffective refactor, ready-job
ordering after fixing a setup blocker, and event replay with conflicting
duplicates after fixing a sequence gap. The latter is an explicit stress case
motivated by the known terminal-callback false match. It is not fresh holdout
evidence for classification accuracy. No comparator, threshold, or Jev prompt
changes are permitted during these trials.

Each task has a written contract, previous and current source, one visible smoke
test, a reference implementation, and a separate grading suite. Verify that the
reference passes every grading assertion and both historical versions fail the
smoke test before freezing. Generate historical records through the real pytest
reporter with the same task, root, and test scope. Preserve the complete records.
The worker receives only the contract, current source, visible test, and historical
records; grading tests and reference implementations stay outside its workspace.
Keep historical diagnoses out of the worker's contract: all methods must infer
the relationship from the same original records.

Compare plain Codex, Codex with deterministic Ratchet, and Codex with deterministic
plus Jev. All receive the same original evidence. Plain Codex reads it from disk;
the other two call the same read-only MCP server, then retrieve the originals.
The method-specific instruction adds only how to obtain the comparison and
original records. It does not supply a repair hint or a claim that retries are
wasteful. Ratchet remains in shadow mode. A wrong or unavailable comparison never
prevents reading originals, making a repair, or running tests.

Use Codex CLI 0.146.0, gpt-5.6-sol, low reasoning, a fresh ephemeral workspace per
run, and normal workspace-write permissions. Do not override command approvals,
ignore security rules, or introduce an execution MCP to work around a declined
shell action. An unscored addition-function preflight must demonstrate an actual
edit and passing tests on the selected worker platform before scored runs start.
Windows and Linux operational checks are reported separately; one platform's
workflow results are not evidence for the other's agent execution.

## Freeze and execution

Freeze this protocol, task files, worker prompts, graders, trial runner, comparator
implementation, dependency versions, prices, and the complete execution schedule
in Git before the first scored run. Independently review the task contracts,
graders, matching, and cost accounting before freezing. A review is not human
validation. Infrastructure preflights use a separate addition task and are retained
as unscored attempts. Do not pilot the scored repairs with a model.

Run five matched triplets per task, 45 workers total, serially. The six permutations
of plain/deterministic/Jev appear two or three times across the 15 triplets. Rotate
tasks between triplets and keep each triplet consecutive. All methods have a
600-second worker limit. A timed-out, declined, or failed worker remains in its
assigned position. No silent replacements, best-of selection, corrective prompts,
or restarting a scored worker after observing its quality. Pause new runs on an
account-wide outage; retain attempts already made. Resume the next unstarted
position after access returns, documenting the interruption.

Start the full-task timer before launching Codex and stop after its process and
owned children have ended. Include MCP startup, selector time, command retries,
provider failures, and any model transport retries in that interval. Record
environment installation and fixture preparation separately as setup costs.
External grading time is separate because it is identical experimental machinery.
Record worker test invocations and repeated commands descriptively; equal commands
alone do not establish wasted work.

## Quality and usefulness gates

The frozen plan in ratchet-plan.md remains authoritative. A successful run requires
an actual implementation edit, unchanged supplied tests and contract, at least one
observed worker test execution, a normally completed worker, and all grading tests
passing. Do not accept a final-message claim as proof. Report passed assertions
and successful runs for every task and method. Quality has no regression only if
the candidate has at least as many successful runs and total passed grading tests
as its comparator on every task. A zero-success task cannot establish usefulness.

Grade in a fresh trusted workspace by copying only the final product.py and the
frozen visible and grading tests. No worker conftest, pytest.ini, added test files,
or plugins enter that workspace. Disable automatic external pytest plugins.
Require the exact frozen test identities and counts with no skips or collection
errors. Compare worker-supplied file hashes before grading; modified supplied
tests, contract, configuration, or original records fail quality. Source edits
must be regular files, not links. The task is scoped to product.py.

Use all assigned runs in time summaries, including failures and capped timeouts.
For each task, divide candidate median by comparator median; take the geometric
mean across the three task ratios. Require either time <= 0.90 with cost <= 1.00,
or cost <= 0.90 with time <= 1.10. Any task's latency ratio > 1.20 fails promotion.
Jev must satisfy quality and performance gates against both plain Codex and
deterministic Ratchet. Missing usage or ambiguous cost bounds cannot pass a cost
gate. Report small-sample limits and all per-task results, not only an aggregate.

Classification already failed its precision and critical-case gates. Even a
positive workflow result cannot enable advisories or filtering in this release.

## Cache and cost accounting

Use reported token usage, including cache reads and writes, rather than character
counts. Preserve raw events privately and publish numeric receipts. Prices checked
2026-09-20: gpt-5.6-sol is $4 per million uncached input tokens, $0.40 cached input,
$20 output, and cache writes are 1.25 times uncached input. Jev input is $0.042 per
million and output is free. Sources: [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
and [Typesafe's Jev announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev).
These are API-equivalent estimates, not the user's Codex subscription bill.

Where input includes cached reads and writes, estimate worker cost as
((input - cached - written) * 4 + cached * 0.40 + written * 5 + output * 20) / 1e6.
Reject negative counts, inconsistent partitions, and duplicate usage events.
Absent cache-write reporting is unknown, not automatically zero; show bounds
between ordinary uncached pricing and all non-read input billed as cache writes.
Jev cost includes every reported provider attempt; report requests, input, output,
elapsed time, errors, and retries separately, then add it to full-task cost.

OpenAI's >272K-input surcharge is per request: input 2x and output 1.5x. Aggregate
CLI usage does not establish individual request sizes. If aggregate input is above
that threshold and per-request accounting is unavailable, show bounds including
the possible surcharge and leave the exact cost gate unverified. A candidate may
pass a bounded cost comparison only if its upper bound satisfies the gate against
the comparator's lower bound. Missing usage from a timeout or failure is unknown;
do not assign it a zero-dollar cost.

Cost aggregation uses the same rule as time: within each task take the median of
all five assigned full-task cost lower bounds and separately of their upper
bounds. Divide the candidate's median upper bound by the comparator's median
lower bound; take the geometric mean of the three task ratios. A missing bound
in any assigned run makes that comparison's cost gate unverified. Never discard
a failed run to obtain a cheaper denominator.

Do not force cache resets, prime only one method, or claim identical cache hits.
Use the same service-managed cache policy, balance order, and report the observed
cache hit fractions and imbalance. Record the CLI version and returned model
identity when available; gpt-5.6-sol is an alias, so pinning the CLI does not freeze
the hosted model's weights.

## Publication boundaries

No raw worker sessions, account identifiers, keys, private paths, or machine
handoffs in Git. Publish frozen authored inputs, implementation, grading results,
aggregate usage, failure categories, and reproducible receipts. Keep unsuccessful
attempts in the denominator. If usefulness fails or cannot be measured, retain the
experimental label and state the failed or unrun gates.
