# Reproduce the prospective repair experiment

The original inputs are frozen at `2c6da13ffb964a77f3e9b0cfd88f7810de23ff7f`.
Use that commit for a reproduction. Later packaging changes do not replace its
first committed protocol, prompts, fixtures, graders, or schedule. The worker
model is a hosted alias; these instructions cannot reproduce historical weights,
service conditions, cache hits, or exact timing.

This runs 45 real Codex workers and may call hosted Jev. It needs a working Codex
sign-in and an explicitly supplied env file containing `TYPESAFE_API_KEY`. The
authored failure records can contain local paths. Review them before enabling
the hosted runs. For a key-free example, use `ratchet demo` instead; that is a
recorded replay and does not measure repair performance.

The original workers use Linux, Python 3.12, pytest 8.4.2, MCP 1.30.0, and Codex
CLI 0.146.0. From a checkout of the repository:

```sh
git worktree add ../ratchet-workflow-reproduction 2c6da13ffb964a77f3e9b0cfd88f7810de23ff7f
cd ../ratchet-workflow-reproduction
uv sync --locked --extra ratchet --extra mcp --python 3.12
npm install --prefix "$HOME/ratchet-eval/codex-cli" @openai/codex@0.146.0
export PATH="$HOME/ratchet-eval/codex-cli/node_modules/.bin:$PATH"
codex login
uv run --no-sync python scripts/freeze_ratchet_workflow.py verify
uv run --no-sync python scripts/prepare_ratchet_workflow_history.py \
  --private-dir "$HOME/ratchet-eval/history"
```

Keep the env file and experiment directories outside Git. Each invocation below
runs only the next unstarted position. Use the same arguments for all 45 runs.
`--reproduce-to` keeps the reproduction separate from the canonical result:

```sh
uv run --no-sync python scripts/run_ratchet_workflow.py \
  --private-dir "$HOME/ratchet-eval/runs" \
  --history-dir "$HOME/ratchet-eval/history" \
  --env-file "$HOME/ratchet-eval/jev.env" \
  --reproduce-to "$HOME/ratchet-eval/reproduction.json"
```

Inspect each completion before starting the next position. Stop new launches if
account access is unavailable. Preserve every attempted position, including
timeouts, declines, tool failures, and incomplete measurements. Do not change the
frozen code, add corrective prompts, switch private directories to rerun a slot,
or select the best attempt. A noncompliant worker cannot support a usefulness
claim even if its patch passes the grader.

If interrupted, inspect the recorded process and owned process group before
removing a stale output lock. Add `--recover-completed` to recover an existing
complete private receipt without running another worker. Where no complete
receipt exists, `--finalize-interrupted` retains a failed row after verifying
that launch did not occur or that the Linux process group is absent. An unknown
launch identity requires further inspection. Never treat a polling timeout or
an old lock alone as proof that a worker stopped.

The final JSON contains all assigned rows and the predeclared assessment.
Raw sessions, patches, exact histories, and grading output remain private.
Publish reviewed numeric receipts and source hashes, with unknown usage left
unknown. Costs are API-equivalent estimates from reported tokens, not a Codex
subscription charge or complete provider billing record. Model transport retry
totals are unavailable; observed notices are reported separately. See the
[frozen protocol](ratchet-workflow-protocol.md) for quality and promotion gates.

The original run required a disclosed startup amendment after its first three
positions. The commands above reproduce the original setup, including its
optional-server behavior. To reproduce the amended setup, use the first commit
containing `results/ratchet/workflow-amendment-1.json`, then invoke
`scripts/run_ratchet_workflow_amended.py` with the same arguments. That wrapper
leaves the first three positions unamended and requires the MCP server from
position 3 onward. It never overwrites the original first-three snapshot or
replaces an attempted worker. See the [amendment](ratchet-workflow-amendment-1.md)
for its operational behavior and interpretation limits.
