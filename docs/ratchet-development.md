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
