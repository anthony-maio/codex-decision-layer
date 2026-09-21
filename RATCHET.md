# Ratchet (experimental)

Ratchet compares pytest failure evidence across attempts. It recognizes matching
observed blockers, preserves the original reports, and abstains when scope or
execution records are incomplete. Jev can classify unresolved pairs after explicit
hosted-upload opt-in. Everything currently runs in shadow mode.

This prototype has not demonstrated fewer wasted retries, lower task cost, or
faster completion. An installed local development plugin has completed a real
Codex task using read-only MCP comparison and exact original retrieval. Automatic
hook capture remains unverified after the first probe's shell commands were
declined by policy. The supported prototype uses explicitly named records.

A separate native Linux Codex preflight has edited a small authored function and
passed its two existing tests. Windows repair passed with a newer desktop-bundled
CLI and workspace-local Python after earlier failed attempts; see the
[Windows setup notes](docs/ratchet-windows.md). These checks are unscored and do not measure
Ratchet's usefulness. A second Linux preflight combined four real MCP calls,
exact original retrieval, an implementation edit, and a passing pytest test.
The three-task prospective repair protocol and runner were frozen at `2c6da13`.
The first triplet passed task quality, but both Ratchet workers missed their
assigned MCP calls. Their failed method checks and unknown costs are retained.
A prospective startup amendment is documented separately; these results cannot
establish the original confirmatory usefulness gate.

## Try the offline replay

From this checkout:

```sh
uv sync --locked --extra mcp --extra ratchet
uv run --no-sync ratchet demo
uv run --offline --no-sync ratchet demo --json
```

The replay needs no API key. It shows recorded decisions and complete normalized
reports from authored development fixtures. It does not execute tests or call a
model. The JSON includes source corpus and receipt hashes, the recorded decision,
and the evidence behind it. This is a replay, not a live agent recording.

## Record and compare your own attempts

Use a task identity shared only by related runs and a new output file per run:

```sh
uv run --no-sync pytest -p evidence_selector.ratchet.pytest_reporter --ratchet-task example --ratchet-output .ratchet/attempt-1.jsonl
uv run --no-sync pytest -p evidence_selector.ratchet.pytest_reporter --ratchet-task example --ratchet-output .ratchet/attempt-2.jsonl
uv run --no-sync ratchet compare .ratchet/attempt-1.jsonl .ratchet/attempt-2.jsonl
```

The output directory is ignored by this repository. In another repository, add
`.ratchet/` to its ignore rules before recording. Raw reports can contain private
source, credentials printed by the application, or other sensitive values. Keep
them local. No reports are uploaded by the default comparator.

Hosted comparison is separately enabled:

```sh
uv run --no-sync ratchet compare .ratchet/attempt-1.jsonl .ratchet/attempt-2.jsonl --jev --allow-hosted --env-file .env
```

The env file supplies `TYPESAFE_API_KEY`. The hosted path sends complete failure
text only for eligible unresolved pairs. That text can contain sensitive values;
review it before opting in. Oversized records abstain without truncation. Provider
errors preserve an unresolved result and all original files; there are no retries.
The optional adapter currently uses Jev 1.13.0 and a development-selected choice
probability threshold of 0.9. This threshold is not a correctness guarantee.

## Read-only Codex tools

The development plugin is in `plugins/ratchet`. Its MCP server exposes
`ratchet_status`, `ratchet_compare`, and `ratchet_evidence`. These tools never
start tests, modify records, or block a command. Original retrieval requires the
SHA-256 from comparison and refuses a record that has since changed.

Configure a directory containing only the records you want the plugin to read:

```sh
uv run --no-sync ratchet configure --root /path/to/record-directory
uv run --no-sync ratchet mcp
```

On Windows, supply a Windows directory path. Configuration is local to your user
account, stores no credential values, and defaults to deterministic shadow mode.
The server refuses linked paths within the canonical root and pins directories
during reads. A concurrent writer can cause a read to fail; it does not produce a
new recommendation. Store completed records in a dedicated directory.

The release candidate manifest launches a tagged package through `uvx`; uv and
Git must be on Codex's PATH. The verified development installation uses an
explicit interpreter and record root. General plugin installation from the
published candidate is still pending. After v0.1.1-rc.2 is published, its intended
installation commands are:

```sh
codex plugin marketplace add anthony-maio/codex-decision-layer --ref v0.1.1-rc.2
codex plugin add ratchet@codex-decision-layer
```

Configure the record root before starting a new Codex task. The tagged launcher
uses the saved root and deterministic shadow mode. It never enables hosted
comparison automatically. Candidate validation is tracked in
[release validation](docs/ratchet-release-validation.md).

Fresh pytest recording, installed CLI comparison, and saved-root MCP
startup pass from isolated wheels on Windows and Linux. Offline checks include
comparison and original retrieval with DNS and new connections denied after
event-loop creation. These checks do not establish automatic event capture.

Hosted MCP comparison requires starting the server with both `--jev` and
`--allow-hosted`; installing the default plugin never opts you into uploads.

## Evidence so far

Thirty independently reviewed authored development pairs contain ten repeated
blockers, ten different blockers, and ten insufficient-evidence cases. Exact
matching found three of ten repeats. Matching explicit exception causes found
all ten with zero false repeat predictions. Jev resolved the remaining eight
different-blocker cases, producing 30/30 combined labels with eight requests.

The stronger deterministic baseline already found every repeated blocker in that
development set. The later frozen public-library holdout exposed a difference:
Jev recovered seven more repeats than that baseline, but the combined system
inherited one critical false match and failed the 95% precision gate (90.9%
observed). The comparator and prompt were not tuned on the holdout. Advisory mode
remains disabled. See [holdout results and failure diagnosis](docs/ratchet-holdout-results.md).

Both corpora contain only two attempts per pair, so neither establishes advisory
usefulness. Independent review is not human validation. The holdout consists of
authored adapters invoking permitted public-library code, not natural agent traces.

See [evaluation plan](docs/ratchet-plan.md), [development protocol](docs/ratchet-development-evaluation.md),
[workflow protocol](docs/ratchet-workflow-protocol.md), and [numeric receipts](results/ratchet/).
The [reproduction instructions](docs/ratchet-workflow-reproduction.md) distinguish
the frozen setup from the [startup amendment](docs/ratchet-workflow-amendment-1.md).
Pytest-xdist is not supported yet.
Interrupted/fail-fast runs, changed test scope, and multiple failures abstain.
