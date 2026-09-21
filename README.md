# Ratchet: compare the failure behind the failure

**An experimental Codex plugin that compares pytest attempts, checks whether the immediate blocker changed, and keeps the original evidence available.**

A different traceback does not always mean a different problem. The same exception message does not always mean the same problem. Ratchet compares completed pytest records using deterministic checks first, with optional [Jev](https://docs.typesafe.ai/) comparison for unresolved pairs. Codex can inspect the decision and retrieve the exact reports behind it.

Everything runs in shadow mode. Ratchet does not block commands, choose patches, or issue anti-thrashing warnings. Saved retries, time, and cost have not been demonstrated.

This repository also contains the earlier evidence-selection experiment with local Eve FP32/Q8 and Jev. Its guide and results are preserved in [Codex Decision Layer](DECISION_LAYER.md).

## Try it without a key

Requirements: Python 3.12 or newer, Git, and [uv](https://docs.astral.sh/uv/).

```sh
git clone --branch v0.1.1 https://github.com/anthony-maio/codex-decision-layer.git
cd codex-decision-layer
uv sync --locked --extra mcp --extra ratchet
uv run --no-sync ratchet demo
```

This is a **recorded replay** of authored development cases. It makes no model calls and executes no tests. Use `uv run --offline --no-sync ratchet demo --json` after installation to see complete normalized reports and recorded decisions without downloading anything.

## What Jev adds, and where it failed

The frozen holdout contains 30 independently reviewed pairs from authored adapters exercising Click, packaging, and more-itertools. It includes changed wrappers, similar messages with different causes, incomplete evidence, and productive progress. These are reproducible public-library cases, not natural agent sessions.

| Method | Repeats detected out of 10 | False repeat predictions | Classification gate |
| --- | ---: | ---: | --- |
| Exact matching | 0 | 0 | Failed recall |
| Stronger deterministic matching | 3 | 1 critical | Failed |
| Deterministic plus Jev | 10 | 1 critical | Failed |

Jev recovered seven repeats that the stronger baseline missed and added no false matches. The combined system still inherited a critical deterministic mistake: two different iterable-length failures shared an error callback. Jev was never called for that already-resolved decision. Combined precision was 90.9%, below the predeclared 95% requirement. The comparator and prompt were not changed after scoring the holdout.

That is a measured semantic benefit with a failed safety gate. Advisory behavior remains disabled. All 45 prospective repair trials are complete: plain Codex and deterministic Ratchet each passed 15/15 repairs, while Ratchet plus Jev passed 14/15. Ratchet plus Jev took 30.7% longer than plain Codex by the geometric mean of per-task median ratios. Unknown costs and retained method failures also prevent the declared usefulness gates from passing. The startup amendment makes this exploratory evidence. [Holdout results](docs/ratchet-holdout-results.md) | [Repair results and independent review](docs/ratchet-workflow-results.md)

## Compare real attempts

In a project with Ratchet and pytest installed, record two related attempts with the same task identity and a fresh output path each time:

```sh
python -m pytest -p evidence_selector.ratchet.pytest_reporter --ratchet-task example --ratchet-output .ratchet/attempt-1.jsonl
# Make your next debugging change, then record another attempt.
python -m pytest -p evidence_selector.ratchet.pytest_reporter --ratchet-task example --ratchet-output .ratchet/attempt-2.jsonl
ratchet compare .ratchet/attempt-1.jsonl .ratchet/attempt-2.jsonl
```

Keep `.ratchet/` out of Git. Reports can contain application output and source text. Local deterministic comparison uploads nothing; hosted comparison requires both `--jev` and `--allow-hosted`. See [setup, hosted use, and supported cases](RATCHET.md).

Ratchet abstains on incomplete runs, changed test scope, and multiple failures. Pytest-xdist is unsupported. A repeated blocker alone does not prove a retry was wasteful.

## Use it from Codex

The plugin exposes three explicit, read-only MCP tools:

- `ratchet_status`: inspect the configured backend and record root.
- `ratchet_compare`: compare two named records in that root.
- `ratchet_evidence`: retrieve originals using the hashes returned by comparison.

The installed development plugin has completed real Codex MCP calls, including exact original retrieval. Linux and Windows repair preflights also passed; Windows needed a newer desktop-bundled CLI and workspace-local Python. [Windows setup](docs/ratchet-windows.md)

The v0.1.1 plugin pins an immutable package commit. Fresh marketplace installs, real Codex MCP calls, exact original retrieval, and cached offline restarts passed on Windows and Linux. RC2's failed tag-based offline startup remains recorded. Follow [release validation](docs/ratchet-release-validation.md) for exact revisions and limits. The supported integration uses explicit records and tool calls; automatic hook capture remains unverified.

## Inspect or reproduce the work

- [Operational and usefulness gates](docs/ratchet-plan.md)
- [Frozen holdout and provenance](docs/ratchet-holdout-protocol.md)
- [Repair experiment reproduction](docs/ratchet-workflow-reproduction.md)
- [Numeric receipts](results/ratchet/)
- [Development record, including failed attempts](docs/ratchet-development.md)

Run the local checks with `uv run --no-sync python -m unittest discover -s tests -v`. The Windows/Linux CI matrix also checks MCP transport and isolated wheel installation. Private sessions, credentials, and machine-specific handoffs are excluded from the repository.
