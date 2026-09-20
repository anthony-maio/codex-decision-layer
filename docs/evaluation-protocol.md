# Release evaluation protocol v1

Declared before collecting new model results. The original 32 synthetic passages are development diagnostics only. This release remains experimental until the gates below pass; failing a usefulness gate does not become a successful optimization claim.

## Corpus and review

Use pinned public source from Requests (Apache-2.0), Flask (BSD-3-Clause), and Click (BSD-3-Clause). Preserve source revisions, exact line ranges, hashes, and licenses. Use at least 18 questions with six candidates each: nine development questions and nine frozen holdout questions, with different target source files across splits. Each repository appears in both splits. Include lexical hard negatives, a false premise contradicted by source, supporting evidence, and critical evidence. No private logs or repositories enter requests.

Review labels independently without model scores. Record disagreements and their resolution before freezing dataset hashes. Separate independent technical review from human ground truth; the latter is not established by an automated review. Freeze cases, labels, prompts, thresholds, baselines, and this protocol before running the holdout. A failed holdout stays failed; later changes need a new holdout.

All candidate source files, including distractors, must be disjoint across splits. Require zero duplicate passage hashes across splits, keep related questions together, and record the overlap audit. Every repository in each split must include critical evidence, false-premise contradictions, and lexical hard negatives. Review category assignments with labels. This small purposive corpus supports measured recall on these cases, not a population-level recall guarantee.

## Methods and bounded budget

Compare retain-all, lexical overlap v1, BM25 top-three (fixed k1=1.5 and b=0.75), TypeSafe Jev 1.13.0, native Eve FP32, and Eve Q8_0. Original relevance-v1 uses drop below 0.1 and confident retention at 0.9. All uncertain candidates remain retained. Baselines receive identical query and passage text. Model input excludes source paths, IDs, and labels.

Eve diagnosis may compare at most two shorter questions and threshold candidates 0.1, 0.2, 0.3, 0.4, 0.5 on development data only. Choose a change only if it misses no relevant or critical evidence and removes at least 15% of evidence bytes across development, including at least 5% in every repository. Otherwise retain the original prompt and threshold. No training is authorized.

The two alternatives are exactly `Does the passage help answer the query?` and `Is the passage relevant to the query, even if it disproves it?`. Keep the original JSON state format. Among eligible development variants choose the greatest byte reduction, then the lowest threshold, then original/first/second prompt order. BM25 tokenizes with the existing lowercase alphanumeric words and stop list, uses per-case candidate document statistics, and breaks score ties by original candidate order. Empty query terms give zero scores. Freeze implementation and protocol hashes alongside dataset hashes in a committed manifest before holdout execution.

Bound new hosted selector calls to 300 requests, one attempt each, at most 512 rendered input tokens per passage for local-model comparisons. Stop on authentication or spending errors. A provider failure is retained evidence and an error, never a correct model decision. Report retries explicitly (default zero). Keep oversized inputs visible and count them as errors, never silently truncate.

## Quality and usefulness gates

- Q1: At least 98% relevant-evidence recall overall on holdout; 100% critical and contradiction recall; at least 95% relevant recall within each repository.
- Q2: Zero transport, model identity, malformed-output, or oversize failures in a successful comparison. Report service reliability separately from accuracy.
- U1: At least 15% total evidence-byte reduction and at least 5% within each repository. This is candidate reduction, not token or cost savings.
- U2: At least one matched end-to-end public-source workflow, with identical task, worker model/version, output budget, correctness rubric, and cache regime. Use five matched trials per method, alternate execution order, and report median and p95 task latency, exact cache-aware input/output tokens, selector overhead, retries, and expansion calls. Require every critical answer and no task-quality regression; require either at least 10% lower total estimated cost with no more than 10% latency regression, or at least 10% lower median latency without higher cost. Record billed cost if returned; otherwise label pricing calculations as estimates. Missing usage or a missing worker service leaves U2 NOT RUN.
- S1: Shadow mode remains default and preserves exact originals. Any deployed filtering requires Q1, Q2, U1, and U2 for that backend, explicit opt-in, recoverable originals, and tested fail-open behavior. Until then, no filtering interface is enabled. Experimental replay may score proposals without changing user-visible evidence.

U2 compares each selector against retain-all. Match prompt wrapper, evidence order, worker settings, fresh context policy, and output limits. Include failed calls and selector usage in total accounting and retain raw provider usage. An isolated benchmark worker may consume proposed subsets before gates pass; the installed plugin still returns all originals. Report all five trial measurements; p95 is the nearest-rank empirical percentile (the maximum of five), not a reliable population tail estimate.

## Runtime and release gates

R1 requires clean wheel installs and CLI/MCP transport tests on Windows and Linux. R2 requires real FP32 and Q8 inference, ready/stop/restart, provider failures, and offline restart after artifacts are cached on both platforms. R3 requires an installed-plugin call in a real Codex task, recorded separately from transport smoke and Desktop UI observation. R4 requires passing CI at the release commit, immutable previous tags, a versioned candidate, public-only receipts, and reproducible commands.

R3 must identify the candidate package pin as well as the historical v0.1.0 installation. Experimental hardening publication requires R1-R4 and S1's shadow/recoverability checks; useful filtering additionally requires Q1/Q2/U1/U2 and filtering fail-open tests for the recommended backend. A failed or missing runtime gate blocks patch publication.

Publish a patch only when its documented release gates pass. A useful-filtering release requires all quality/usefulness gates as well. Failed usefulness keeps the experimental label and disables filtering; runtime hardening can be described only as runtime hardening. Unrun gates stay open, and no stable optimization release is inferred from this protocol.
