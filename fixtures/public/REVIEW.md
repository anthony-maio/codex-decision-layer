# Public corpus review

The author labeled these cases before any model scores were collected. An independent reviewer then read only the unlabeled review input, source copies, and provenance. That review classified every candidate, identified decisive evidence and hard negatives, and checked exact line preservation. This is independent technical review, not human-validated ground truth.

All 108 excerpt instances matched source lines and all six source hashes matched provenance. There are 36 unique excerpts in six pools. Each pool supports three different questions. No candidate source file or excerpt hash crosses the split boundary. This is a small purposive source-navigation benchmark, not a representative random sample of repository work.

We adjudicated disagreements before freezing or scoring. The relevance rule includes supporting control flow and contradictory source comments, even when a shorter answer could omit them. Accepted additions:

- dev-flask-1: retain the nested-key storage continuation because loader failures can flow through it.
- holdout-requests-3: retain the downstream urlopen call as evidence that the selected target is used.
- holdout-flask-3: retain the modified-attribute comment and save-session continuation. The comment says a cookie is written only when modified, while should_set_cookie permits permanent-session refresh. Both sides of this real source conflict are marked critical and contradictory.
- holdout-click-1: retain the parser wrapper that proceeds from option handling to positional arguments.
- holdout-click-2: retain both value-extraction continuations because the question asks how explicit-value processing works.
- holdout-click-3: retain the continuation that returns the omitted-value sentinel.

The neutral Choice question does not assert a false premise, so its contradiction marker was removed. Every other author relevance judgment matched the independent review. Hard negatives concern adjacent operations with overlapping vocabulary: redirect authentication versus methods, configuration APIs, type normalization, proxy authentication versus URL selection, cookie expiration versus refresh, and parser matching versus separators. Some are easier than others; holdout-requests-2 has a comparatively weak negative pool.

Review limitations: no human label approval, only three Python repositories, correlated questions within source pools, no dynamically assembled retrieval corpus, and no population-level confidence claim. Source provenance and license files accompany the data. Regenerate with `python scripts/build_public_corpus.py`; verify the frozen hashes before scoring.
