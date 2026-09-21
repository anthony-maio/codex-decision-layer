# Ratchet development record

## Feasibility checkpoint 1 - 2026-09-20

Branch: `feat/ratchet`, based on the existing experimental release candidate.
Working-time budget: 16 hours total; first checkpoint under one hour (coarse bound).
No Jev calls, new training, or holdout scores in this checkpoint.

The installed Windows Codex CLI identifies itself as 0.146.0 and reports hooks
stable and enabled. Its tagged source includes PostToolUse with tool identity,
input, response, task and turn identifiers. This establishes API presence only.
Source: https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/hooks/schema/generated/post-tool-use.command.input.schema.json

A real CLI probe requested two separate pytest runs of an authored fixture that
raises ConnectionRefusedError during setup. Both shell calls were declined by
Codex policy before execution. No hook events were recorded. The worker exited
successfully after reporting the denial; that is not integration success.
The hook event and installed-plugin gates remain NOT VERIFIED. The probe's first
version used invocation-only hook trust bypass; this does not bypass shell policy.
Independent review identified incomplete hook-source isolation, so the bypass
was removed rather than expanding it. Raw CLI logs remain outside Git.

The recorder now captures exact pytest phase reports in an exclusively created
local file and records completed session status. The comparator detects duplicate
records, incomplete runs, mixed failure sets, stage progression, and matching
exception plus traceback/source evidence. Changed exception values or origins
remain unresolved. Task identity, runner options, and selected test identities
must match before comparison. Fail-fast or interrupted runs remain incomplete;
duplicate or impossible phase reports are rejected. It
never emits an advisory warning: blocker identity alone cannot establish that a
retry is wasteful. Pytest-xdist is explicitly unsupported in this first version.

Independent review requested separate advisory labels, legitimate-retry guards,
scenario-level split isolation, explicit metric denominators, balanced matched
triplets, incremental Jev comparison, and exact promotion rules. Those requirements
were incorporated before corpus construction. Review does not constitute human
ground truth or acceptance of the final product.

Verification: Windows full suite 53/53 passed; Debian WSL2 new reporter integration
suite 9/9 passed. These tests execute real pytest processes and compare exact
recorded evidence. They do not establish Jev quality or real Codex integration.
CI now installs the optional ratchet extra so these tests cannot silently skip
for a missing pytest dependency in its Windows/Linux matrix.

Next: strengthen the event probe's normal
trust and command-approval path; construct and independently label development
cases before attempting hosted semantic comparison. The two-day feasibility
decision remains open. Do not interpret this checkpoint as a release.

## Feasibility checkpoint 2 - 2026-09-20

Thirty authored development pairs were produced by executing pytest 8.4.2, then
reviewed without author labels or model scores. Review agreed on ten same, ten
different, and ten insufficient-evidence labels. One duplicate pair was corrected
and re-reviewed before scoring. Cases are explicit-raise fixtures, not failures
observed in public repositories. All have only two attempts; none qualifies for
an advisory. Raw records remain private, normalized corpus and review are public.

The review suggested a stronger deterministic exception-chain baseline. It was
implemented before the first hosted call. Exact matching found 3/10 repeats;
explicit-chain matching found 10/10 with zero false repeats. The stronger baseline
correctly labeled 22/30 overall and abstained on eight different-blocker cases.
Jev resolved those eight correctly, for 30/30 combined development labels. It used
4,948 input tokens and 424 output tokens across eight requests, with 3.445 seconds
total measured provider latency, zero retries, and zero provider errors.

The predeclared threshold grid selected 0.9; all four tested thresholds gave the
same labels. CLI live comparison uses 0.9. The experiment's original default-0.8
receipt and its full probability distributions remain unchanged and reproducible.
No holdout has been built or scored. Jev has added zero repeated-blocker detections
beyond the stronger baseline in this corpus; incremental anti-thrashing usefulness
is not established. Advisory and full-workflow gates remain open.

A key-free recorded replay now includes three examples and complete normalized
reports. Its recorded nature and lack of demonstrated savings are stated in the
CLI and Ratchet documentation. Provider fault tests cover timeout, quota, server
failure, malformed distributions, oversized inputs, and explicit hosted opt-in.
Live Codex integration remains NOT VERIFIED; no attempt was made to route around
the earlier shell-policy denial.

Checkpoint verification: Windows full suite 63/63 passed; Debian WSL2 Ratchet
suite 19/19 passed. Fresh wheel environments on Windows and Linux ran the packaged
replay with Python DNS/connect disabled. Existing evidence-selector CLI and MCP
smokes also passed in those environments; that is not Ratchet MCP integration.
Wheel identity is recorded by SHA-256. The development wheel still carries the
base package version; it is not a new published release candidate or changed tag.

## Feasibility checkpoint 3 - 2026-09-20

The read-only MCP integration works in an installed local development plugin on
Codex CLI 0.146.0. A fresh real task called status, compared two public recorded
pytest attempts, and retrieved the exact first original using its comparison
hash. The receipt verifies tool results against packaged replay bytes and records
implementation hashes. The local launcher uses an explicit development
interpreter and record root; published plugin installation is still pending.
This proves a callable comparison tool. It does not prove automatic hook capture,
fresh test execution inside Codex, or fewer wasted debugging attempts.

Independent review identified blank/relative saved roots and a check-then-open
path race. Saved roots now require a nonempty absolute path. POSIX reads traverse
pinned directory descriptors without following links. Windows reads pin every
ancestor with data-read access and exclude write/delete sharing. The reviewer
also reproduced in-place junction mutation with attribute-only handles; the
final data-read handles prevent it. The regression test attempts a competing
writer while the root is pinned and verifies that ordinary child creation still
works. Post-fix review found no remaining must-fix issue in this scope.

Windows: 72 tests passed. Linux: 72 tests ran, 70 passed, with two Windows-only
checks skipped. Both platforms passed isolated wheel installation and real
Ratchet stdio comparison/original retrieval with DNS and new connections denied
after event-loop creation. Windows needs an initial loopback socketpair for its
event loop, so this is not described as an OS-level network isolation test.
CI now runs the Ratchet protocol smoke explicitly and from the isolated wheel.

The successful Codex probe took 53.5 seconds and reported 117,935 input tokens,
including 92,672 cached input tokens, plus 672 output tokens. Its full host tool
catalog and context are included. Those numbers are an integration receipt,
not selector overhead, a matched workflow, or a savings measurement. No price
estimate is inferred from them. Private task logs and local settings stay outside
Git. The development wheel retains the base version and is not published.

Next: freeze the public-source holdout and its independent labels, then run the
predeclared comparisons and prospective workflow trials. Jev still has no
demonstrated incremental repeated-blocker detection benefit over the stronger
deterministic baseline. Shadow mode remains the only enabled behavior.

## Feasibility checkpoint 4 - 2026-09-20

The independently reviewed public-library adapter holdout is frozen at `941949d`.
It contains 30 pairs in ten related scenarios across Click, packaging and
more-itertools, with ten labels per relationship class. Source commits, licenses,
actual pytest-child import identities and raw/normalized record hashes are
recorded. Pre-score review tightened partial-result gates, committed-input
verification, exact child provenance, path-only normalization and atomic receipts.
No classifier ran until the final packet and scoring code were committed.

Exact matching detected 0/10 repeats. The stronger deterministic baseline detected
3/10 with one critical false match. Deterministic plus Jev detected 10/10 with
the same inherited false match: 90.9% precision and 100% recall. Jev recovered
seven correct repeats missed by the baseline without adding false positives,
passing the incremental gate. The combined classification gate still failed its
95% precision and zero-critical-false-match requirements. Advisory stays disabled.

The false match joins too-few and too-many iterable branches at a shared error
callback. Jev was not called for that already-resolved baseline decision. No
comparator or prompt revision was made after observing the failure; a future
revision requires independent development evidence and a new holdout. Independent
post-score audit verified counts, accepted labels, source hashes and gate failures.

Fourteen provider calls used 13,369 input and 742 output tokens, with 5.560 seconds
total provider latency, no errors and no retries. These are comparator-only
measurements, with provider cache usage and billed cost unavailable. Linux
reproduction of both deterministic methods matched every Windows label, reason,
evidence hash and metric. No second Jev scoring run was performed.

Checkpoint verification: Windows full suite 78/78 passed; Linux 78 tests ran,
76 passed and two Windows-only checks skipped. These checks do not establish
hosted CI or workflow usefulness.

Full prospective workflow quality, latency and cache-aware worker cost remain
open. Pair classification is now measured; debugging usefulness is still
unproven. See `ratchet-holdout-results.md` for the failed gates and receipt paths.

## Feasibility checkpoint 5 - 2026-09-20

Native Linux Codex completed an unscored addition-function repair in 23.1 seconds.
The original function subtracted its arguments; the resulting file adds them.
The worker executed the existing unittest suite once and both tests passed.
Exact final file content, unchanged test content, a completed file-change event,
and actual command output were checked separately from the worker's final message.
Reported usage was 87,494 input tokens, including 72,832 cached reads and zero
cache writes, plus 526 output tokens. This is an execution prerequisite, not a
Ratchet speed or cost comparison.

The first native Linux attempt failed because its sign-in could not refresh.
The user signed in again before the successful attempt. Windows' unscored repair
attempt reached a 240-second limit with no completed shell commands, no final
usage, and the source unchanged. Both terminal outcomes are retained. Its root
cause is unresolved; the timeout alone does not identify a sandbox or MCP fault.
No permission restrictions were disabled to obtain the Linux success. The CLI
version used for both platforms was 0.146.0; installing the native Linux package
also resolved a WSL launcher that had pointed at a Windows npm package.

The prospective protocol remains DRAFT. Three authored repair tasks cover invoice
arithmetic, ready-job selection after setup progress, and event replay with a
generic error callback. The event task is deliberately motivated by the known
holdout weakness and cannot serve as new independent classification evidence.
No scored repair has been run with a model. Original comparator and Jev prompt
remain unchanged after holdout scoring.

Independent review found that the invoice reference rejected a very large valid
shipping amount. Precision now includes shipping digits, with a regression case.
It also led to removing diagnostic hints from worker task descriptions, requiring
fresh trusted grading with exact frozen test identities, and spelling out median
cost-bound ratios and missing-usage treatment. Both platforms now verify all six
broken historical versions fail their smoke tests and all three references pass
93 visible-plus-grading tests in total.

The accounting implementation covers a balanced 45-run schedule, both Jev
comparators, cache reads/writes, uncertain per-request surcharges, complete-run
coverage, failed-run retention, per-task quality, and latency regressions. Review
reproduced a false pass from inverted or infinite cost bounds; numeric validation
now rejects those receipts. Ten focused metric checks pass on Windows and Linux.
The private worker utility also preserves timeout and duplicate-usage states.

Checkpoint checks: Windows full suite passed 90/90; Linux ran 90 checks with 88
passing and two Windows-specific skips. Final independent closure confirmed the
reported design, fixture, and metric issues were resolved. Trial execution and
its enforcement remain outside that review's completed scope.

Next: implement and independently verify the trial runner and MCP timing capture,
freeze the complete protocol and inputs, then run the 15 matched triplets. General
published-plugin installation, Windows repair execution, exact-commit CI, workflow
usefulness, and release preparation remain open. Advisory behavior stays disabled.

## Feasibility checkpoint 6 - 2026-09-20

The installed Ratchet plugin was called directly in this task: status, comparison,
and complete retrieval of both originals matched the authored replay bytes.
A separate unscored native Linux worker combined the same four MCP calls with an
actual addition repair and a passing pytest test in 34.2 seconds. MCP calls took
36.3 milliseconds in total, including proxy overhead; this is an integration
receipt, not a matched usefulness result. Authentication was revalidated with a
successful live request before proceeding.

The prospective runner now keeps a durable assigned-slot claim and an exclusive
experiment lock. Interruptions remain in the denominator. Recovery never launches
a replacement worker. Atomic receipts preserve the previous complete state;
unknown launch identity requires inspection. Independent review verified these
repairs alongside complete original-reading checks, same-child import provenance,
and test proof tied to the final edited source. Model transport retries are not
fully exposed by the CLI; observed notices and unknown exact counts are reported
separately from measured Jev requests and retries.

Windows passed 105 unit checks. Linux ran the same 105 checks with 103 passing and
two Windows-only skips. Real metered stdio comparison and complete original
retrieval passed on both platforms. CI now includes that smoke check. These local
results do not establish hosted CI or a successful Windows repair worker.

All three historical failure pairs were recorded with verified project imports
without running classification or scored model repairs. The earlier preparation
review remains a historical receipt at commit 7b29191; the final runner review
identifies its own input hashes. The next step is the committed prospective freeze
and the 45 assigned workers. The known classification failures remain unchanged,
so advisory behavior remains disabled regardless of workflow results.

## Feasibility checkpoint 7 - 2026-09-20

The prospective experiment was frozen at `2c6da13`. Its first triplet completed
all repairs, but both Ratchet methods missed their MCP calls and used the
original-record fallback. They retain failed method checks and unknown costs.
Unscored diagnostics reproduced the readiness failure while direct MCP calls
worked. Requiring the server at startup passed a real addition repair preflight;
a second check with only that one config change passed as well.

Independent review approved a prospective infrastructure amendment at `69b791e`.
It preserves the first three rows and every original frozen input. Starting with
slot 3, only deterministic and Jev commands add the required-server flag. The
existing lock protects amendment claims, rows, recovery, and final audit. A
required-server startup failure can abort the worker and must count as failure;
this differs from the comparator's fail-open behavior after provider errors.
All 45 positions remain assigned. The experiment is amended exploratory work,
and its failed original usefulness gates cannot be rescued by selecting a subset.

Nine of 45 workers have completed, covering the first triplet on each task.
All nine passed task quality. Five passed the frozen method verifier. The two
plain queue/event workers did read both complete originals, but batched the
reader after other inspections; the verifier expects the entire command output
to be JSON and rejected those outputs. A separate byte-and-hash audit documents
that measurement limitation without changing their frozen rows or gates.
The event task exercised one real Jev call: 1,121 input and 53 output tokens,
529.8 milliseconds, zero retries, and all 29 task grading tests passed. This is
not evidence of a speed or cost benefit. The remaining 36 workers are unrun at
this checkpoint.

Windows repair now has a passing unscored receipt. CLI 0.146.0's stalled commands
were not fixed by removing inherited desktop routing. The tested desktop-bundled
CLI 0.155.0-alpha.2.6 executed commands and edited the source, but its venv could
not start a base Python in user AppData. The same Python 3.12.11 installed beneath
the workspace passed direct read-only sandbox checks, including a derived venv.
The full Codex repair then changed only the implementation and passed both
existing tests in 47.1 seconds. No sandbox permissions were widened. The failed
attempts remain in the receipts, and the working configuration is documented.

Windows passed 113 unit checks; Linux passed 111 with two Windows-only skips.
Expanded clean-wheel checks then passed on both platforms: fresh pytest failure
recording, installed CLI comparison with unchanged originals, saved-root MCP
startup through the installed executable, and the existing offline replay and
protocol checks. The wheel still has the base development package version and
is not a new release. Exact-commit hosted CI, published-plugin installation,
the completed workflow schedule, and versioned release preparation remain open.
