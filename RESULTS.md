# Evaluation history

Current candidate: [v0.1.1 validation](docs/release-validation.md). The public-source holdout passed Jev's relevance gates, but the matched Codex workflow failed usefulness. Eve retained everything. Shadow mode remains the only deployed behavior. The results below are the preserved v0.1.0 synthetic baseline, not the current release gate.

## First evidence-selector run

September 20, 2026. Live TypeSafe Jev 1.13.0, using the same eight constructed cases as a deterministic lexical baseline. Each case contains four passages. Fourteen of the 32 passages are labeled relevant; nine are marked critical. Labels are authored fixture expectations, not independently reviewed production ground truth.

| Measurement | Lexical baseline | Jev |
| --- | ---: | ---: |
| Relevant passages retained by proposal | 10/14 | 14/14 |
| Critical passages missed by proposal | 2/9 | 0/9 |
| Proposal precision | 52.6% | 66.7% |
| Proposed passage-byte reduction | 30.0% | 23.4% |
| Actual passage bytes removed | 0 | 0 |
| Total selector latency | 0.417 ms | 12875.996 ms |
| Model requests scored | 0 | 32 |
| Provider errors | 0 | 0 |

Jev preserved relevant paraphrases the baseline missed. It proposed dropping the injected instruction passage. It also retained seven irrelevant passages, including a keyword-heavy UI passage that scored 0.58. This is an encouraging relevance result with a conservative threshold, not a general accuracy guarantee.

The Jev run reported 10949 input tokens and 704 output tokens. At the published $0.042 per million input tokens with free output, the input-price estimate is $0.000459858 for this 32-request replay. The API did not return a billed dollar amount; this is a rate-based estimate, excluding the separate MCP smoke calls. [TypeSafe pricing](https://docs.typesafe.ai/models)

Mean per-passage time was approximately 402 ms; the median four-passage case took 1584.759 ms. Requests ran sequentially and the timing includes HTTP overhead. No Codex task was run with evidence removed, so end-to-end speedup, main-model token savings, and task success under filtering are NOT MEASURED. Shadow mode can itself add context and latency.

Saved evidence:

- [Jev replay receipt](results/jev.json)
- [Baseline replay receipt](results/baseline.json)
- [Fixture set and labels](fixtures/relevance.json)

Validation status:

- Core selection, labels, exact source preservation, provider failures, invalid probabilities, endpoint boundaries, dotenv behavior, Eve prompt limits, GGUF readout, and plugin configuration: 30 automated tests PASS.
- Actual stdio MCP connection -> tool call -> live Jev -> original evidence returned: PASS.
- Evidence expansion through MCP: PASS.
- Outside-root read through MCP: REFUSED.
- OpenRouter: request/response contract tested locally; live provider run NOT RUN.
- Eve: original checkpoint, native FP32 server, F16 GGUF, and Q8_0 GGUF all ran locally with zero errors on the fixture replay. See below.
- Codex Desktop UI observation: NOT RUN. Built-in tools are not intercepted.
- Public GitHub marketplace registration and plugin installation through Codex CLI: PASS for v0.1.0.
- Installed plugin launcher -> tagged package -> stdio MCP -> local Q8 model: PASS. [Receipt](results/plugin-smoke.json).
- GitHub CI for the tagged source: Windows and Linux unit tests and MCP smoke checks PASS. [Run](https://github.com/anthony-maio/codex-decision-layer/actions/runs/35531307917).

Next useful measurement: independently label a larger set of real retrieval candidates, freeze the labels, then replay Jev and Eve on the same inputs. End-to-end task trials should follow before evidence filtering is enabled. The current run does not justify changing permissions or dropping context automatically.

## Local checkpoint and quantization

The pinned Hugging Face export is `anthonym21/qwen3-0.6b-rlcd-decision` at revision `b327ec5efb5fdbf8bfafa3b369720ac5f6434b05`. Its saved head exactly matched the corresponding tied embedding rows before conversion. Original weights were preserved.

| Backend | Relevant retained | Retained total | Brier score | Total selector time |
| --- | ---: | ---: | ---: | ---: |
| Original Decider FP32, CPU | 14/14 | 32/32 | 0.281101 | 11.30 seconds |
| Native FP32, CPU | 14/14 | 32/32 | 0.281101 | 9.23 seconds |
| GGUF F16, RTX 4080 | 14/14 | 32/32 | 0.280582 | 3.57 seconds |
| GGUF Q8_0, RTX 4080 | 14/14 | 32/32 | 0.281010 | 2.44 seconds |

Every local run scored all 32 passages without errors. All proposed zero exclusions at the unchanged 0.1 threshold. Preserving everything prevents missed evidence here but gives no filtering benefit. Jev's corresponding proposal precision was 66.7%; all Eve variants were 43.75%. The original model needs task-specific evaluation or adaptation before it can be recommended for relevance filtering.

Native FP32 matched the original Decider to a maximum absolute probability difference of 1.252e-6. F16 GGUF differed by at most 0.005842; Q8_0 differed by at most 0.017433, with mean difference 0.006680. No classification at 0.5 or retention proposal flipped on this set. This is a small parity sample, not a quantization calibration guarantee.

Timing includes local HTTP and sequential requests. The CPU and GPU paths differ in hardware, numerical kernels, and inference implementation; these timings do not isolate a quantization speedup. They also do not measure downstream Codex performance. The first reference attempt began during server startup and was discarded; the published reference receipt is the complete, error-free rerun after readiness.

Q8_0 artifact: 639442432 bytes. F16 artifact: 1198177792 bytes. [Conversion receipt](results/conversion.json), [reference receipt](results/eve-fp32.json), [native receipt](results/eve-native-fp32.json), [Q8 receipt](results/eve-q8_0.json), [probability comparison](results/q8-parity.json).
