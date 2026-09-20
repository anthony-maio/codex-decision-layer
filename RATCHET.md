# Ratchet (experimental)

Ratchet compares pytest failure evidence across attempts. It recognizes matching
observed blockers, preserves the original reports, and abstains when scope or
execution records are incomplete. Jev can classify unresolved pairs after explicit
hosted-upload opt-in. Everything currently runs in shadow mode.

This prototype has not demonstrated fewer wasted retries, lower task cost, or
faster completion. Live Codex hook integration remains unverified after the first
probe's shell commands were declined by policy.

## Try the offline replay

From this checkout:

```sh
uv run --extra ratchet ratchet demo
uv run --extra ratchet ratchet demo --json
```

The replay needs no API key. It shows recorded decisions and complete normalized
reports from authored development fixtures. It does not execute tests or call a
model. The JSON includes source corpus and receipt hashes, the recorded decision,
and the evidence behind it. This is a replay, not a live agent recording.

## Record and compare your own attempts

Use a task identity shared only by related runs and a new output file per run:

```sh
uv run --extra ratchet pytest -p evidence_selector.ratchet.pytest_reporter --ratchet-task example --ratchet-output .ratchet/attempt-1.jsonl
uv run --extra ratchet pytest -p evidence_selector.ratchet.pytest_reporter --ratchet-task example --ratchet-output .ratchet/attempt-2.jsonl
uv run ratchet compare .ratchet/attempt-1.jsonl .ratchet/attempt-2.jsonl
```

The output directory is ignored by this repository. In another repository, add
`.ratchet/` to its ignore rules before recording. Raw reports can contain private
source, credentials printed by the application, or other sensitive values. Keep
them local. No reports are uploaded by the default comparator.

Hosted comparison is separately enabled:

```sh
uv run ratchet compare .ratchet/attempt-1.jsonl .ratchet/attempt-2.jsonl --jev --allow-hosted --env-file .env
```

The env file supplies `TYPESAFE_API_KEY`. The hosted path sends complete failure
text only for eligible unresolved pairs. That text can contain sensitive values;
review it before opting in. Oversized records abstain without truncation. Provider
errors preserve an unresolved result and all original files; there are no retries.
The optional adapter currently uses Jev 1.13.0 and a development-selected choice
probability threshold of 0.9. This threshold is not a correctness guarantee.

## Evidence so far

Thirty independently reviewed authored development pairs contain ten repeated
blockers, ten different blockers, and ten insufficient-evidence cases. Exact
matching found three of ten repeats. Matching explicit exception causes found
all ten with zero false repeat predictions. Jev resolved the remaining eight
different-blocker cases, producing 30/30 combined labels with eight requests.

The stronger deterministic baseline already found every repeated blocker in this
set. Jev has not established an incremental repeat-detection benefit. These fixtures
also contain only two attempts each, so they cannot establish advisory usefulness.
This review is not human validation, a frozen holdout, or a public-repository result.

See [evaluation plan](docs/ratchet-plan.md), [development protocol](docs/ratchet-development-evaluation.md),
and [raw numeric receipts](results/ratchet/). Pytest-xdist is not supported yet.
Interrupted/fail-fast runs, changed test scope, and multiple failures abstain.
