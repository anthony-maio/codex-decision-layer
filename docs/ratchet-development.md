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
