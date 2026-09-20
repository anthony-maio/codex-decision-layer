# Ratchet holdout v1 results

Jev recovered seven repeated blockers missed by the stronger deterministic
baseline. The combined system still failed the classification gate: it inherited
one critical false match from that baseline, producing 90.9% repeat precision
against a required 95%. Advisory mode remains disabled. No task-level time or
cost benefit has been established.

The corpus, accepted independent labels, protocol and code were frozen in commit
`941949d93e455ac3ad2d9838aca0a469fb0309b2` before scoring. The comparator and prompt
remain unchanged from `b60386f`; Jev used the development-selected threshold 0.9.
Every method completed all 30 cases. Each was scored once in the original
experiment; deterministic reproduction on Linux matched all labels, reasons,
evidence hashes and metrics from Windows.

| Method | Correct repeat detections | False repeat detections | Repeat precision | Repeat recall | All labels correct | Classification gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Exact | 0/10 | 0 | Undefined | 0% | 12/30 | FAIL |
| Explicit-cause deterministic | 3/10 | 1 | 75% | 30% | 15/30 | FAIL |
| Deterministic plus Jev | 10/10 | 1 | 90.9% | 100% | 28/30 | FAIL |

Jev's incremental recovery gate passed: seven additional correct repeat
detections, exceeding the required three, with zero added false positives.
That gate is separate from the full system's precision and critical-case gates.
On the 14 unresolved pairs actually sent to Jev, it returned seven correct same
labels, six correct different labels, and one abstention. It added no false
repeat prediction. No threshold, prompt or comparator adjustment was made after
seeing holdout results.

## The critical false match

`holdout-fixed-result-cardinality-different` first supplies too few values to
`more_itertools.strictly_n`, then supplies too many. Both failures invoke the
same authored error callback, which raises the same generic ValueError. The
innermost frame and message match, but the earlier traceback frames identify
different cardinality branches. The stronger baseline discards that distinction
when accepting a matching terminal cause signature. It predicts the same blocker
incorrectly. The combined path inherits that answer because Jev is called only
for unresolved comparisons.

The related `one` case also uses identical error text for too few and too many
items. The baseline abstained there, and Jev remained below the frozen threshold.
That abstention is preserved. Matching error text or a common callback is not
enough to justify stopping a retry. The original source and traceback remain
recoverable for every decision.

This diagnosis does not authorize tuning on this holdout. The current experiment
and its failed gates remain frozen. A future comparator revision would need
independent development evidence and a fresh holdout before promotion.

## Scope and measured overhead

These are authored adapters exercising pinned Click, packaging and more-itertools
code, not naturally collected debugging sessions or upstream bugs. The 30 pairs
cover ten related scenario groups across three repositories. All 30 labels were
independently reviewed without predictions; this is not human validation. Wilson
intervals in the receipts describe pair counts and do not establish population
reliability under this purposive, correlated sample.

The hosted comparison made 14 calls using 13,369 input tokens and 742 output
tokens. Total measured provider latency was 5.560 seconds; the full scoring loop
took 5.696 seconds, excluding validation/setup and interpreter startup. There
were zero provider errors and zero retries. Cache usage was not reported by
Jev, and no billed-dollar amount is inferred. Those are comparator measurements,
not worker savings or end-to-end debugging latency.

Every pair has only two attempts. Advisory eligibility and prospective workflow
usefulness remain unevaluated, and classification failure already blocks advisory
promotion. Shadow mode is the only enabled behavior. The next experiment must
measure full tasks with original evidence available and include this fallible
comparison behavior in the task-quality assessment.

## Receipts and reproduction

Original numeric receipts are in `results/ratchet/holdout-v1/`. Linux reproduction
is verified by `results/ratchet/holdout-linux-reproduction.json`. Full permitted
source notices, executed-code hashes, raw/normalized record hashes and blind
review artifacts are in `fixtures/ratchet/holdout-v1/`.

For exact historical reproduction, check out the freeze commit above in a
separate directory and follow its holdout README. Later package or implementation
changes may correctly fail the old freeze validator. Reproduction output goes
to a new directory outside the checkout and is labeled separately. It never
replaces the original experiment. Private raw logs, local settings and keys are
not part of the public packet.
