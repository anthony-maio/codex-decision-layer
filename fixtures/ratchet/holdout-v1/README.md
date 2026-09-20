# Ratchet holdout v1

Thirty failure pairs from ten deliberately triggered scenarios in three public
Python libraries. This is an authored adapter benchmark, not a collection of
upstream bugs or natural Codex failures. See the source commit IDs, full license
notices and executed-code hashes in `corpus.json` and the accompanying files.

The independent reviewer received only randomized `review-input.json`, with
adapter sources, records and retry intent. Descriptive case IDs, tags, author
labels, comparator code and predictions were withheld. `review-map.json` maps
those blind IDs back to cases. `independent-review.json` preserves the review;
`review.json` records accepted labels and the exact reviewed hashes. This is not
human validation. Related pairs are not independent failure mechanisms.

`freeze.json` binds the full experiment to committed source and evidence before
scoring. It remains immutable. The harness checks every required input against
both the worktree and the original freeze commit. Each method has one exclusive
receipt location under `results/ratchet/holdout-v1`; interrupted and partial
receipts are preserved, and incomplete coverage cannot pass a promotion gate.

## Reproduce

From the repository root, score the checked-in frozen corpus separately:

```sh
uv run --locked python scripts/evaluate_ratchet_holdout.py --freeze fixtures/ratchet/holdout-v1/freeze.json --method exact --reproduce-to /outside/checkout/receipts
uv run --locked python scripts/evaluate_ratchet_holdout.py --freeze fixtures/ratchet/holdout-v1/freeze.json --method deterministic --reproduce-to /outside/checkout/receipts
uv run --locked python scripts/evaluate_ratchet_holdout.py --freeze fixtures/ratchet/holdout-v1/freeze.json --method jev --reproduce-to /outside/checkout/receipts --allow-hosted --env-file /private/jev.env
```

On Windows, use Windows paths for the external receipts and private env file.
The Jev method requires explicit hosted upload consent and a TypeSafe key. The
deterministic methods need neither a model nor a network connection. Scoring
receipts are created once per directory. Reproduction receipts are explicitly
labeled and never overwrite the original scored experiment checked into Git.

To recreate runner evidence, clone the three repositories listed in
`scripts/build_ratchet_holdout.py` into a source directory and check out their
exact commit IDs. Create a Python 3.12 environment, install
`runner-requirements.txt`, then install those three checkouts in editable mode.
Run `scripts/build_ratchet_holdout.py --source-dir SOURCE --private-dir RAW
--output-dir NEW_OUTPUT`. RAW must be outside this repository; NEW_OUTPUT must
not exist. It checks source checkout cleanliness, package versions and module
origins in the actual pytest child process. All raw records stay in RAW.

The public corpus replaces run/task identities, root paths, frame-path prefixes
and timing. It preserves source expressions and exception messages. Four current
records deliberately omit finish; six pairs contain two failing tests. Each
record has its raw and normalized SHA-256. Raw hashes vary across regenerated
runs because run IDs and timings differ. Executed source byte hashes may differ
with checkout line endings; commit IDs identify the public source revision.
Copied license bytes are preserved exactly in Git. The frozen corpus, rather
than a newly regenerated sample, is the input for the scored comparison.

Three pre-score construction passes tightened provenance and path normalization;
the adapters, author labels, comparator and Jev prompt were unchanged. The first
pass used broad slash normalization, the second restricted it to ordinary frame
paths, and the final pass covered generator frames and verified child imports.
No method was scored between these passes. Review was reconfirmed on the final
evidence before freeze.

All cases contain only two attempts, and retry intent is diagnostic or unknown.
This corpus cannot pass the advisory gate. Recorded timing is zeroed, so latency
measurements in scoring receipts concern the comparator invocation only. They
do not measure debugging time, worker token savings, or billed cost.
