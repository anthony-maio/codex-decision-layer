# Local models and GGUF conversion

Checkpoint: [anthonym21/qwen3-0.6b-rlcd-decision](https://huggingface.co/anthonym21/qwen3-0.6b-rlcd-decision), pinned to `b327ec5efb5fdbf8bfafa3b369720ac5f6434b05`.

## Run the original checkpoint

From the repository:

```sh
uv run --extra local eve-decision-server --device cpu
```

First start downloads the checkpoint and verifies its weight hashes. Subsequent inference stays local. Use `--checkpoint /path/to/export` for an existing copy, `--port` to choose a port, or `--threads` to control CPU threads. Defaults: port 8765, eight CPU threads.

Wait for `GET http://127.0.0.1:8765/health` to return `status: ok`, then:

```sh
uv run evidence-selector --provider eve evaluate fixtures/relevance.json --output results/local-eve.json
```

`--device cuda` requires a CUDA-enabled PyTorch build. Recorded FP32 runs used PyTorch 2.14.0+cpu and Transformers 5.17.0 on Windows. A GPU being installed does not guarantee the default PyTorch wheel supports CUDA.

Native inference uses the original saved FP32 decision head and training prompt. Verification used upstream `rlcd.decide.Decider` at commit `ce5ebf627058b65acfc41d49e0e334a722a14ba5`. Maximum probability difference: 1.252e-6. The optional `--engine reference` requires that repository's `rlcd` package in the environment.

## Run the Q8 GGUF

Download `eve-qwen3-0.6b-rlcd-q8_0.gguf` from the [v0.1.0 release](https://github.com/anthony-maio/codex-decision-layer/releases/tag/v0.1.0) into `models/`. Size: 639442432 bytes (about 610 MiB). SHA-256:

```text
49523f391d1408655b00b0c041a405efbb0ed343685f9415057cd6e04d8aac9a
```

Install [llama.cpp](https://github.com/ggml-org/llama.cpp). Tested: build 7836, commit `0c21677e4`, CUDA on an RTX 4080. Newer server versions may change response fields; rerun the checks when upgrading.

Terminal one:

```sh
llama-server -m models/eve-qwen3-0.6b-rlcd-q8_0.gguf -ngl 99 --host 127.0.0.1 --port 8766 -c 1024 --parallel 1 --no-webui
```

Use `-ngl 0` for CPU. On Windows, invoke `llama-server.exe`. Wait for `/health` to report ready.

Terminal two, from this repository:

```sh
uv run gguf-decision-server --llama-endpoint http://127.0.0.1:8766 --port 8767
```

Terminal three:

```sh
uv run evidence-selector --provider eve --endpoint http://127.0.0.1:8767/v1/systemone --model eve-q8_0 evaluate fixtures/relevance.json --output results/local-q8.json
```

The adapter is necessary. Chat templates, greedy yes/no generation, top-p truncation, or a different temperature change the readout. It uses the saved space-prefixed A/B token IDs, exact raw prompt tokens, temperature 1, no cache reuse, and a constrained one-token request. Grammar also permits a standalone space, so A/B probabilities are renormalized together. Missing letter probabilities are errors.

Both servers bind to loopback. Stop with Ctrl+C. This is a local development service, not an authenticated multi-user deployment.

## Reproduce the conversion

Use the original export, a llama.cpp checkout, and its quantizer:

```sh
uv run --extra local --with sentencepiece --with protobuf python scripts/convert_decision_gguf.py --source /path/to/decision-export --source-revision b327ec5efb5fdbf8bfafa3b369720ac5f6434b05 --llama-cpp /path/to/llama.cpp --quantize /path/to/llama-quantize --output models/eve-gguf
```

Recorded converter revision: `9d1ceead3163704639a285e86dbe9c7977f3bda0`. The command creates a reconstructed HF staging directory, F16 and Q8_0 GGUFs, a decision manifest, and a receipt. Allow roughly 5 GB of extra disk beyond the original cached weights. The original checkpoint is preserved.

It verifies source hashes, tokenizer letter IDs, and exact equality between the decision head and tied embedding rows. Unsupported or untied exports are rejected. GGUF reconstructs a vocabulary projection; the adapter supplies the bounded API.

| Candidate versus original Decider FP32 | Mean absolute probability change | Maximum | Classification flips at 0.5 |
| --- | ---: | ---: | ---: |
| Native FP32 | 0.000000407 | 0.000001252 | 0 |
| GGUF F16 | 0.001547 | 0.005842 | 0 |
| GGUF Q8_0 | 0.006680 | 0.017433 | 0 |

These 32-passage differences combine runtime arithmetic and, for Q8, quantization. They are not a general calibration guarantee. The original checkpoint did not separate irrelevant passages well here; reducing model size does not fix that task mismatch.

Weights are Apache-2.0 licensed. The license, source reference, conversion notice, and hashes accompany the release. Prompts longer than 512 tokens remain outside this experiment's supported range.
