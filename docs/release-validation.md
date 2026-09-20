# v0.1.1 experimental hardening candidate

This release improves installation and local-server operation. It does not establish a useful Codex optimization. The workflow usefulness gate failed, and no filtering interface is enabled.

## Frozen relevance evaluation

The [protocol](evaluation-protocol.md) and [manifest](../fixtures/public/frozen.json) were committed before new model scores. [Blind review and adjudication](../fixtures/public/REVIEW.md) preceded the freeze. The data comes from pinned Requests, Flask, and Click source with licenses preserved: 18 questions, 108 candidate instances, 36 distinct excerpts in six source pools. Nine questions are development cases and nine are holdout cases. No source file or excerpt hash crosses splits. Independent technical review is not human-validated ground truth; this small correlated corpus does not establish a population recall guarantee.

| Holdout method | Relevant retained | Critical missed | Proposed byte reduction | Q1 | Q2 | U1 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Retain all | 18/18 | 0 | 0% | PASS | PASS | FAIL |
| Lexical overlap | 18/18 | 0 | 10.16% | PASS | PASS | FAIL |
| BM25 top three | 14/18 | 1 | 47.36% | FAIL | PASS | PASS |
| Jev 1.13.0 | 18/18 | 0 | 37.95% | PASS | PASS | PASS |
| Eve FP32 | 18/18 | 0 | 0% | PASS | PASS | FAIL |
| Eve Q8_0 | 18/18 | 0 | 0% | PASS | PASS | FAIL |

All model comparisons completed without errors or retries. Every shadow receipt removed zero actual bytes. See [all receipts](../results/v0.1.1/). FP32 used Windows CPU, Q8 used the existing Windows RTX 4080 server, and Jev was hosted. Their selector latency totals are observations on different runtimes, not a controlled quantization speed comparison. The separate lifecycle tests use CPU on both platforms.

## Why Eve retained everything

The original development prompt produced relevant probabilities from 0.5166 to 0.7762 and irrelevant probabilities from 0.4472 to 0.8090. Irrelevant median probability (0.6209) exceeded relevant median probability (0.6133). None approached the conservative 0.1 exclusion boundary. This is poor separation for this relevance task, not a reason to reinterpret retain-all as high quality.

The predeclared search covered the original prompt, two shorter questions, and thresholds 0.1 through 0.5. No variant met all improvement criteria. The original prompt at 0.5 removed only 7.5% of bytes; the second alternative at 0.5 removed 48% but missed seven relevant passages. The original policy was retained before holdout scoring. No training or holdout tuning occurred.

[Simple positive/negative controls](../results/v0.1.1/eve-diagnostic-controls.json) separate cleanly in both runtimes, and historical native/reference parity is within 0.00000126. Together these observations make an inverted A/B readout or quantization-only defect unlikely. They support a task-fit/calibration problem on the measured relevance inputs; they do not establish its training cause.

## Matched Codex workflow

The [workflow protocol](workflow-protocol.md) was committed before ten fresh Codex worker trials. The task explains Flask's session-refresh condition, empty-session behavior, and an actual documentation/code conflict. Five retain-all runs were paired with five live Jev runs, alternating order. GPT-5.6 Sol used low reasoning and the same output schema. All ten outputs passed the structured rubric and independent blind explanation review. No tools, expansion calls, retries, or provider failures occurred.

| Measurement | Retain all | Jev plus worker |
| --- | ---: | ---: |
| Correct answers | 5/5 | 5/5 |
| Median complete task | 9.436 s | 11.261 s |
| Empirical p95 (maximum of five) | 9.927 s | 12.237 s |
| Total API-equivalent estimate | $0.354594 | $0.427805 |
| Worker input tokens per trial | 20422 | 20422 |

Jev retained all six passages in this task. Median latency rose 19.3%, and the cache-aware estimate rose 20.6%. One baseline run received 20224 cached-input tokens; the other nine runs received no cache reads. The same service-managed cache policy was used, but actual hits were unequal. This confounds a causal cost comparison; it does not create evidence of savings. Even ignoring that hit, identical worker input plus selector overhead offers no measured input-token benefit here. Cache writes were zero. Full numeric usage, selectors, answers, and timings are in the [workflow receipt](../results/v0.1.1/workflow.json). Prices are estimates, not subscription bills. The readiness probe and unsupported-model probe are setup overhead outside task totals, as declared in the protocol.

U2 is **FAIL**. Jev's relevance gates alone do not authorize filtering. Eve also fails U1. No backend is approved for deployed filtering. Shadow mode, exact originals, source expansion, and provider fail-open behavior remain the release behavior.

## Runtime gates

| Gate | Candidate status |
| --- | --- |
| R1: isolated wheel, CLI and MCP on Windows/Linux | PASS for 0.1.1rc1; install receipts identify exact version |
| R2: FP32/Q8 start, infer, stop, same-port offline restart | PASS for 0.1.1rc1 on Windows and Debian WSL2; offline scope below |
| R3: installed plugin in real Codex | v0.1.0 verified in this task; candidate verification pending |
| R4: exact candidate CI and immutable versioning | Pending remote CI and candidate pin verification |
| S1: shadow default and recoverable originals | Automated checks pass; filtering remains absent |

Normal runtime checks bind only loopback, exercise actual inference, authenticate graceful shutdown, verify the owned child stops, then restart on the same ports. Offline checks prohibit external Python DNS/connect and set the model hub offline flag; Q8 reads its local GGUF. The host network is not physically disconnected, and the compiled llama child is not network-sandboxed. That scope is recorded in every receipt. Linux here is Debian under WSL2, not a separate physical Linux machine. GPU portability and Desktop settings UI observation are not claimed.

## Reproduce

```sh
uv sync --extra mcp --locked
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python tests/smoke_mcp.py
uv build --wheel
uv run --no-sync python scripts/validate_install.py --wheel dist/codex_evidence_selector-0.1.1rc1-py3-none-any.whl --output results/local-install.json
uv run --no-sync python scripts/evaluate_public.py --method retain-all --split holdout --output results/local-holdout-baseline.json
uv run --no-sync python scripts/evaluate_public.py --method jev --split holdout --env-file .env --output results/local-holdout-jev.json
```

Model replay submits only public excerpts. One Jev split uses 54 requests, with no retries. Freeze verification runs before calls. Existing output files are refused. Preserve the checked-in holdout and results; changes need a new benchmark version. Source regeneration is `python scripts/build_public_corpus.py`; on Windows normalize generated JSON CRLF to LF before checking byte hashes, or regenerate under Linux. Git's LF attributes preserve the frozen bytes in clean checkouts.

For model lifecycle checks, install the local extra and run `scripts/validate_runtime.py --engine fp32 --output results/local-runtime.json`. For Q8 supply `--engine q8 --llama-server ABSOLUTE_EXECUTABLE --gguf ABSOLUTE_GGUF`. Logs are ignored by Git; publish sanitized JSON receipts only. Use `scripts/measure_workflow.py --env-file .env --private-dir OUTSIDE_REPOSITORY --output results/local-workflow.json` for the bounded ten-trial workflow. This invokes Codex and hosted Jev and can consume inference quota; it does not train a model.

The patch publication gate is R1-R4 plus S1. An experimental hardening patch may publish with U1/U2 failures stated above; it must not claim useful filtering or lower Codex bills. Existing tags are immutable. The paused compaction fork, upstream repositories, private logs, and social accounts are outside this release.
