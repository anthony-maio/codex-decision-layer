# Ratchet public-source holdout protocol

Declared before holdout construction or scoring. Comparator checkpoint: `b60386f`.
The deterministic parser/comparator and Jev prompt are frozen at this checkpoint.
Jev uses the development-selected threshold 0.9 and model Jev 1.13.0. No threshold
grid, prompt adjustment, or comparator improvement is permitted on this holdout.
If a defect requires a change, preserve this experiment and report it separately.

## Provenance and split

Construct 30 pairs through authored pytest adapters calling pinned public library
code: Click 8.1.8, packaging 25.0, and more-itertools 10.8.0. These are deliberately
triggered public-library failures, not upstream bugs, naturally collected agent
traces, or evidence that an upstream project wastes retries. Include exact commit
IDs and license notices with the normalized corpus. Keep all three repositories
entirely in holdout; none was used in Ratchet development. The earlier authored
explicit-raise fixtures remain development-only. Shared relationship categories
are necessary, but no development source template or causal scenario is reused.

The target is ten same-blocker, ten different-blocker, and ten insufficient pairs.
Library scenarios cover CLI choices, ranges, tuple arity and required options;
version, specifier, requirement and marker grammar; and iterable cardinality.
Include two identical-message hard negatives at different cardinality branches,
productive setup-to-call progress, downstream assertion failures, incomplete
records, and multiple simultaneous failures. Preserve contradictions and every
reported failure. Do not select examples based on model or baseline predictions.

"Same blocker" means the same immediate failing operation and constraint, with
the decisive evidence present in both runs. Changing an invalid argument while
still violating the same identified constraint can leave the immediate blocker
unchanged. It does not establish a wasted retry. Different violated constraints
or progress to a later failing stage count as different blockers. Unclear causes,
changed test selection, missing completion, or mixed failures require abstention.

## Review and freeze

Execute each adapter with pytest 8.4.2, automatic third-party plugins disabled,
and the frozen reporter. Store exact raw records privately. Public normalization
replaces run IDs, task/root paths and timing, preserves traceback lines and
library code, and records any deliberate incomplete-record transformation.
Store the adapter source for both attempts and the public source provenance.

Randomize case order and replace descriptive IDs for independent review. Supply
the exact normalized evidence and adapter source but no author labels, model
predictions, scores, comparator implementation, or descriptive scenario tags.
The reviewer labels relationship, decisive evidence and advisory eligibility.
Resolve disagreements before freezing without consulting either comparator.
Record exclusions and label changes; do not silently force class balance.
Independent review is not human validation. Every case has two attempts, so this
pair holdout cannot pass the separate three-attempt advisory gate.

Before scoring, commit the corpus, review, accepted labels, normalization rules,
provenance, source hashes, comparator/prompt hashes and evaluation-script hash.
Each method is scored once: exact matching, stronger explicit-cause deterministic
matching, and deterministic plus Jev. Provider failures count as abstentions;
authentication/quota failures stop the experiment and are recorded without
automatic retries. Preserve partial results. Never reuse a scored holdout to tune.

## Reporting

Apply the previously declared precision >= 95%, recall >= 70%, zero critical
false-repeat gates. Jev must recover at least three correct repeated blockers
missed by the stronger deterministic baseline without adding false positives.
Report counts, per-case results, class distribution, precision/recall uncertainty,
unresolved-subset results, all provider calls, input/output usage, elapsed latency,
and failure counts. Report this public-library adapter corpus separately from the
authored development corpus. No result here establishes savings or anti-thrashing
usefulness. Advisory sequences and matched prospective workflows remain separate
gates under `ratchet-plan.md`.
