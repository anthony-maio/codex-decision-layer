# Ratchet feasibility and release plan

Status: experimental, feasibility work started 2026-09-20. No usefulness claim.

Ratchet compares successive test failures and records whether the immediate blocker
appears unchanged. Its first supported runner is pytest. It preserves exact local
evidence, treats progress separately from a passing exit code, and emits at most
one advisory message for a repeated blocker until new evidence or a cooldown.
Shadow mode is the default. Ratchet never blocks commands, chooses patches, or
declares a task impossible.

## Feasibility deadline

Spend at most two working days on the first feasibility pass. Establish real
installed Codex event capture, reliable runner records, and a development-set
semantic benefit. If integration is not viable within that time, evaluate the
previously agreed Review Merge fallback. Track actual working time and decisions
in the development record; elapsed unattended time is not working time. Interpret
two working days as 16 hours of active engineering, with checkpoints at 4, 8,
and 16 hours. Stop extending the feasibility experiment at the final checkpoint.

## Implementation order

1. Capture a real PostToolUse event in an isolated Codex task on the installed
   version. Verify completion, exit status, command identity, and failure output.
   Record what is unavailable or truncated. Do not infer complete evidence from
   a hook that only exposes a preview.
2. Add a pytest reporter to record collection/setup/call/teardown stages, test
   identities, outcome, and traceback, with exact originals stored locally.
   Partial, cancelled, mixed, and malformed runs must abstain where evidence is
   insufficient. Keep task/repository/run scopes separate.
3. Implement deterministic fingerprints first. Add Jev only for unresolved
   comparisons, using same blocker / different blocker / insufficient evidence.
   Untrusted evidence is data, never instructions or generated commands.
4. Provide a CLI, a Codex plugin, source retrieval, and a clearly labeled
   recorded replay requiring no API key. Hosted mode requires explicit setup;
   no implicit upload or hosted fallback. Keep provider failures advisory and
   fail open. Never replace original tool output.
5. Evaluate shadow classification before opt-in advisory execution. Run matched
   prospective workflows before claiming saved retries, time, or cost.

## Predeclared evaluation gates

Freeze datasets, provenance, independent label review, runner/parser version,
prompt, model, thresholds, and protocol hashes before holdout scoring. Split by
whole task/repository, not near-duplicate error text. Development exploration
must be recorded. A scored holdout is never a tuning set. Group authored cases by
fixture/template and causal scenario; variants cannot cross the split.

The first corpus targets at least 60 failure pairs from permitted public sources
or explicitly labeled reproducible authored fixtures: 30 development and 30
holdout, balanced across same/different/insufficient. Each split must include
productive setup-to-assertion progression, legitimate retries, different causes
with matching messages, wrapper changes around the same cause, multiple failures,
and incomplete evidence. Report authored and public-source results separately.
Independent review is not represented as human validation. Reviewers label both
blocker relationship and advisory eligibility independently. A legitimate retry
can have the same blocker but be ineligible for a warning. Mixed failures abstain
in v1; do not select a convenient failure while hiding another. Freeze the warning
policy separately: at least three completed attempts in the same task/test scope,
same blocker on both adjacent comparisons, no observed stage advancement, and no
explicit diagnostic/retry justification. One warning per unchanged blocker;
reset only on changed evidence, with a minimum three-attempt cooldown. Unknown
retry intent is not sufficient to enable an advisory warning.

Classification gate: precision of same-blocker recommendations at least 95%,
recall at least 70%, and zero warnings on designated critical productive-progress,
legitimate-retry, or insufficient-evidence cases. Precision is correct same-blocker
predictions divided by all same-blocker predictions; recall is correct same-blocker
predictions divided by all labeled same-blocker cases. No predictions fails recall.
Apply these gates to both deterministic and combined methods. Report counts and
uncertainty; a small benchmark
does not prove population reliability. Jev must recover at least three correct
holdout same-blocker cases missed by the deterministic baseline without adding
false positives. Report unresolved-subset and full-corpus combined results. If it
does not, do not promote Jev to advisory behavior. Advisory precision uses the
separate eligibility labels, not blocker relationship labels, and must be at least
95% with at least five proposed advisories evaluated. Zero advisories cannot pass
promotion. Critical productive-progress, legitimate-retry, and insufficient cases
must have zero advisories.

Operational gate: Windows and Linux unit/integration checks; real Codex plugin
invocation; isolated clean install; no-key replay; recoverable exact evidence;
duplicate/concurrent event handling; timeout, quota, malformed reply, and
connection failures; no command blocking; shadow default and explicit opt-in.
No private logs, credentials, absolute workstation paths, or handoffs in Git.

Workflow gate: at least three distinct tasks, five matched triplets per task for
plain Codex, deterministic Ratchet, and deterministic plus Jev. Freeze task
rubrics and execution order before runs. Balance the six possible method orders
across the 15 triplets, with counts differing by no more than one. Include one
productive debugging task. Every task must retain quality; thresholds below apply
to the geometric mean of per-task median ratios, with per-task latency regressions
over 20% failing promotion. Assess Jev against deterministic Ratchet and plain
Codex separately; it must pass against both to claim incremental usefulness.
Require no task-quality regression and either median full-task latency reduced
at least 10% with cost no higher, or cache-aware estimated cost reduced at least
10% with latency no more than 10% higher. Count selector overhead, retries,
cache reads/writes, and setup separately. Report each task and aggregate results.
Replay classification cannot establish a prospective workflow improvement.

## Release

Reuse the existing Decision Layer repository on a separate Ratchet branch.
Preserve its frozen experiments and tags. A release candidate needs appropriate
tests, exact-commit CI, installation instructions, a reproducible demonstration,
and a requirement-by-requirement receipt. If semantic or workflow gates fail,
retain the experimental label and publish the precise limits. Operational safety,
original recovery, privacy, or install failures block any release. Classification
or advisory-eligibility failures restrict that backend to shadow mode. Workflow
failure permits only an explicitly experimental release, with no savings or
anti-thrashing claim. Do not market an
anti-thrashing outcome based solely on classifying recorded failures.

The public presentation should explain one behavior, provide a short real demo,
show the deterministic comparison and counterexamples, and make the engineering
work inspectable. Social posting remains outside this task.
