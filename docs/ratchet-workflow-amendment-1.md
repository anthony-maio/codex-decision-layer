# Prospective startup amendment after the first triplet

The first three assigned workers completed under the original freeze at
`2c6da13`. All passed task quality. Plain Codex satisfied its evidence-reading
method; deterministic Ratchet and Jev did not call the configured MCP tools.
Their worker messages reported unavailable tools and used the local fallback.
Both failed method compliance, and their full cost bounds remain unknown. The
complete three-row snapshot and its canonical digest are retained unchanged.

Unscored addition preflights reproduced the readiness failure. A direct MCP
client completed comparison and exact original retrieval. Numeric tracing also
observed a successful initialization handshake and returned tool list in real
Codex use. Marking the server required made the real preflight complete four MCP
calls, exact original retrieval, an actual source edit, and a passing test. A
second check changed only `mcp_servers.ratchet_trial.required=true`, with the
original startup timeout and trial environment; it passed as well. This evidence
supports a readiness problem in the integration. It does not identify an upstream
source-code defect or establish that all future startups will succeed.

Starting at slot 3, deterministic and Jev commands append exactly this config
override before the stdin argument:

```text
-c mcp_servers.ratchet_trial.required=true
```

Plain commands remain identical. No scored position is restarted or replaced.
The original schedule, all 45 assigned positions, worker prompts, fixtures,
comparator, Jev prompt, grader, prices, cost rules, and 600-second timer remain
unchanged. Original frozen files and tags are preserved. The additive wrapper
and this amendment must be independently reviewed and committed before slot 3.

A required MCP server can abort the worker when startup fails. That is an
operational policy change, and any such attempt counts as failed. It is distinct
from the comparator's behavior after a provider error, which continues to
preserve evidence and return an unresolved shadow decision. Do not describe
required startup as fail-open worker execution.

The wrapper adds amendment attribution under the original experiment lock,
including pending claims, completed rows, and recovered or interrupted rows.
It verifies the original first three rows and rejects later rows or claims
without attribution. Continuing through the old entry point after this amendment
is detectable misuse: stop and inspect; never erase or rerun those positions.

Publish the complete experiment as **amended exploratory evidence**. The original
confirmatory usefulness requirement is not established. Existing failed method
and cost gates remain failures; unchanged assessment includes every position.
Post-amendment subsets can describe observed behavior but cannot replace the
full denominator or support a passing usefulness or causal savings claim.
Unscored diagnostics are reported separately as development/setup work.

Use `scripts/run_ratchet_workflow_amended.py` with the original runner arguments
for subsequent positions and recovery. The wrapper validates the first committed
amendment and original freeze before running. The ordinary reproduction runner
continues to reproduce the unamended setup; clearly distinguish those outputs.
