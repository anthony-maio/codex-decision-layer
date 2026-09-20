# Codex Decision Layer

**Run small semantic decisions through Jev or a local Eve model, and measure what happens before changing an agent's behavior.**

A CLI, a Codex plugin, and an MCP server for testing a practical question: which parts of an agent's work actually need its main model?

The first experiment is evidence selection. Give the tool a question and a few files. It reads the original passages, asks a decision model which ones are relevant, and returns the source text alongside the proposed decisions. Everything starts in shadow mode. No evidence disappears.

Use a TypeSafe key, an OpenRouter key, the open-source Eve checkpoint on your own machine, or a deterministic keyword baseline. Local inference works with the original FP32 checkpoint and an optional **639 MB Q8_0 GGUF**.

**Current finding:** Jev preserved every relevant passage in the small fixture set while proposing some exclusions. Eve ran successfully, but retained every passage at the same conservative threshold. The local runtime works; useful relevance filtering with this checkpoint remains an open problem.

## Why build this?

An agent writes code, retrieves documents, checks process state, and makes judgments about what to do next. Those operations have different requirements. File existence and exit status belong in code. Writing a patch needs a generative model. Choosing whether a short passage answers a specific question may fit a small decision model.

The accounting matters. A check inserted after Codex has proposed a tool call adds work unless it prevents something more expensive later. We need to measure avoided model turns, downstream context, retries, and missed evidence. A cheap classifier alone does not establish a cheaper agent.

This repository provides the adapters, explicit tools, and replay receipts needed to test that idea. It does not claim a 200x speedup or replace Codex's planner.

## Quick start: entirely local

Requirements: Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). The FP32 path runs on CPU; GPU use requires a compatible PyTorch build.

```sh
git clone https://github.com/anthony-maio/codex-decision-layer.git
cd codex-decision-layer

# Downloads the pinned model on first use and verifies its weight hashes.
uv run --extra local eve-decision-server --device cpu
```

Wait for `Eve ready at http://127.0.0.1:8765/v1/systemone`. In another terminal, from the repository:

```sh
uv run evidence-selector --provider eve evaluate fixtures/relevance.json --output results/local-eve.json
```

Original model weights occupy about 2.4 GB. Subsequent starts use the Hugging Face cache. Pass `--checkpoint /path/to/decision-export` to use an existing local copy. Inference makes no hosted model calls.

For the smaller llama.cpp path, see [Run the Q8 GGUF](docs/local-models.md#run-the-q8-gguf). [Release assets](https://github.com/anthony-maio/codex-decision-layer/releases/tag/v0.1.0) include the GGUF, hashes, and conversion provenance.

## Run Jev or the baseline

```sh
# No model, no network.
uv run evidence-selector evaluate fixtures/relevance.json --output results/local-baseline.json

# .env contains TYPESAFE_API_KEY=...; it is ignored by Git.
uv run evidence-selector --provider typesafe --env-file .env evaluate fixtures/relevance.json --output results/local-jev.json

# Or use OPENROUTER_API_KEY in the same file.
uv run evidence-selector --provider openrouter --env-file .env evaluate fixtures/relevance.json --output results/local-openrouter.json
```

The hosted replay makes 32 short paid requests. Only fixture queries and passage text are submitted. API keys are read into the local process, never included in result files. Checked-in results contain synthetic fixtures and model receipts, not private Codex transcripts.

| Backend | Interface | Where inference runs |
| --- | --- | --- |
| Baseline | Lexical overlap | Local CPU |
| TypeSafe Jev | `/v1/systemone`, pinned `jev-1.13.0` | TypeSafe |
| OpenRouter Jev | `/api/alpha/decisions`, `typesafe/jev-1.13` | Hosted |
| Eve FP32 | Saved decision head, PyTorch | Your machine |
| Eve Q8_0 | llama.cpp plus bounded probability adapter | Your machine |

These decision endpoints are not chat-completions endpoints. See the [TypeSafe API](https://docs.typesafe.ai/api) and [OpenRouter recipe](https://openrouter.ai/docs/cookbook/building-agents/gate-tool-calls-with-jev).

## Install the Codex plugin

Configure the provider and the directory the evidence tools may read. This example uses the local FP32 server:

```sh
uv run evidence-selector --provider eve configure --root /absolute/path/to/your/project
codex plugin marketplace add anthony-maio/codex-decision-layer --ref v0.1.0
codex plugin add decision-layer@codex-decision-layer
```

Start a new Codex task after installation. Ask it to use Decision Layer on explicitly selected files. The plugin adds:

- **`shadow_evidence`**: read passages, score relevance, and return every original passage with its proposed decision.
- **`read_evidence`**: expand source lines without a model call.
- **`evidence-selection` skill**: guidance on uncertainty, contradictions, and the difference between model failure and a successful decision.

The plugin launches the tagged package through `uvx`, so uv and Git must be available to Codex. Settings live in `~/.codex/decision-layer.json`; `DECISION_LAYER_CONFIG` can select another file. Settings contain paths and environment-variable names, not key values. Configure again to change providers; previous settings are backed up.

For Jev, configure with `--provider typesafe --env-file /absolute/path/to/.env`. For Q8, use `--provider eve --endpoint http://127.0.0.1:8767/v1/systemone --model eve-q8_0`. Put those options before `configure`.

The plugin adds tools called explicitly. It does not intercept built-in tools, bypass approvals, or modify conversation history. CLI installation and MCP transport are separate from Desktop UI observation; see [validation status](RESULTS.md).

## Read real files

```sh
uv run evidence-selector --provider eve retrieve --root . --query "What happens when a provider request fails?" --file evidence_selector/core.py --chunk-lines 12
```

Each passage preserves its original UTF-8 text, line number, source path, and content-derived ID. Name the files explicitly. Paths outside the root, `.env` files, and Git internals are rejected. Limits: 16 files, 64 passages, and 256000 passage bytes. Large pools are rejected; individual oversized model inputs are retained without clipping.

`select input.json` also accepts an existing candidate set:

```json
{
  "query": "Why are writes lost at shutdown?",
  "candidates": [
    {
      "id": "shutdown",
      "source": "service.py",
      "start_line": 24,
      "text": "def shutdown(self):\n    self.worker.cancel()\n"
    }
  ]
}
```

`candidates` and `returned_ids` always retain every input passage. `proposed_drop_ids` is diagnostic only. Scores below 0.1 propose exclusion; scores from 0.1 to below 0.9 remain uncertain and retained. Thresholds are provisional. Provider errors retain evidence and are recorded as errors.

## What we measured

Eight constructed scenarios, 32 passages, 14 relevant passages, nine critical passages. Same questions, labels, and thresholds across backends. Labels are authored fixture expectations, not independently reviewed production ground truth.

| Backend | Relevant retained | Critical missed | Proposed byte reduction | Errors |
| --- | ---: | ---: | ---: | ---: |
| Keyword baseline | 10/14 | 2/9 | 30.0% | 0 |
| Jev 1.13.0 | 14/14 | 0/9 | 23.4% | 0 |
| Eve FP32 reference | 14/14 | 0/9 | 0% | 0 |
| Eve native FP32 | 14/14 | 0/9 | 0% | 0 |
| Eve GGUF Q8_0 | 14/14 | 0/9 | 0% | 0 |

Eve's perfect retention comes from retaining everything. It should not be read as successful filtering. Its Brier score on this set was about 0.281, versus Jev's 0.0374; these numbers describe this fixture, not general model quality.

Q8 changed no 0.5 classifications or retention proposals compared with the reference on these 32 passages. Its maximum absolute probability difference was **0.01743**. The lightweight FP32 implementation matched the reference within **0.00000126**. Quantization can still matter near a threshold.

Sequential Jev replay took 12.88 seconds. Q8 took 2.44 seconds on an RTX 4080. Reference FP32 used CPU and took 11.30 seconds. These are separate hardware/runtime observations; they do not isolate quantization speedup or establish faster Codex tasks.

[Full results](RESULTS.md) | [Saved receipts](results/) | [Fixture labels](fixtures/relevance.json) | [Conversion details](docs/local-models.md)

## The local decision readout

The checkpoint stores a transformer body and 26 rows of a decision head. A Noul question maps ` A` to true and ` B` to false. The FP32 server runs the original prompt format, reads those two logits, and normalizes them into a probability. It generates no answer text.

GGUF conversion verifies that the saved head equals the corresponding tied embedding rows, reconstructs the standard Qwen3 vocabulary projection, and quantizes it to Q8_0. The adapter requests one constrained token from llama.cpp, reads A/B probabilities, and renormalizes only those two IDs. It ignores the sampled answer. Both paths reject fully rendered prompts above 512 tokens.

The GGUF itself is not structurally decision-only. The adapter exposes a bounded API. [Hashes and provenance](results/conversion.json) make the conversion inspectable.

## Development

```sh
uv sync --extra mcp --locked
uv run python -m unittest discover -s tests -v
uv run --extra mcp python tests/smoke_mcp.py
uv run python scripts/compare_receipts.py results/eve-fp32.json results/eve-q8_0.json
```

Tests cover evidence preservation, failure handling, probability validation, path boundaries, dotenv handling, GGUF readout, and plugin settings. The MCP smoke test starts a real stdio server, calls both tools, and checks an outside-root read. Live model evaluations are separate from CI.

Next work is model suitability: independently label real retrieval cases, compare shorter task-specific questions, and train or calibrate against held-out evidence-selection data. Then test complete tasks with filtering enabled, measuring missed evidence, expansion calls, cache behavior, latency, and downstream cost together.

Code: [MIT](LICENSE). Model weights: [Apache-2.0](MODEL-LICENSE.txt). See [NOTICE.md](NOTICE.md) for sources. This is an independent experimental integration.
