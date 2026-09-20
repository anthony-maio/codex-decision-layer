# v0.1.0: Local decision models and shadow evidence selection

This first experimental release includes a CLI, an MCP server, and a Codex plugin for comparing bounded relevance decisions. Backends include TypeSafe Jev, OpenRouter Jev, native local Eve FP32, and local Eve through llama.cpp.

The attached Q8_0 GGUF is converted from `anthonym21/qwen3-0.6b-rlcd-decision` revision `b327ec5efb5fdbf8bfafa3b369720ac5f6434b05`. It is 639442432 bytes and is distributed under Apache-2.0. The project code is MIT licensed. The conversion receipt records hashes and source provenance.

On 32 synthetic passages, Q8 changed no retention proposals or 0.5 classifications compared with the original FP32 checkpoint. Maximum absolute probability difference: 0.017433. The local checkpoint retained every passage at the conservative relevance threshold, so this release demonstrates local execution and probability comparison, not useful filtering by Eve or a Codex speedup.

Shadow mode preserves all evidence. Automatic filtering and automatic routing of built-in Codex tools are not enabled. See the README for installation and RESULTS.md for measured limitations.

Artifact SHA-256:

```text
49523f391d1408655b00b0c041a405efbb0ed343685f9415057cd6e04d8aac9a  eve-qwen3-0.6b-rlcd-q8_0.gguf
```
