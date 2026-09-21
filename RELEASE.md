# v0.1.1: Experimental pytest failure comparison

Ratchet adds explicit read-only Codex tools for comparing completed pytest attempts and retrieving the original reports. Deterministic checks run first; hosted Jev comparison requires explicit evidence-upload opt-in and only handles unresolved eligible pairs. A key-free recorded replay ships in the package. This release remains experimental and shadow-only.

On the independently reviewed frozen holdout, Jev recovered seven repeated blockers missed by the stronger deterministic baseline without adding false matches. The combined system inherited one critical deterministic false match and failed its 95% precision requirement. Advisory behavior stays disabled. All 45 repair trials are complete and independently reviewed: plain Codex and deterministic Ratchet passed 15/15 repairs each, and Ratchet plus Jev passed 14/15. Both Ratchet methods were slower than plain Codex. Unknown costs, retained method failures, and the disclosed startup amendment remain part of the result. All usefulness comparisons failed. See the [full repair results](docs/ratchet-workflow-results.md).

The patch wheel passed Windows and Linux clean installation, fresh pytest recording, installed CLI comparison, saved-root MCP startup, and offline original recovery. Fresh marketplace installs also passed real Codex status, comparison, and original-retrieval calls on both platforms. The pinned uvx launcher passed cached offline restart. Final local suites passed 116 Windows checks and 114 Linux checks, with two Windows-only skips. Hosted Windows/Linux CI covers unit checks, MCP transport, wheel build, and isolated installation. The release's attached publication receipt binds its final commit, CI run, and artifact hash. Follow the [Ratchet release gates](docs/ratchet-release-validation.md) for exact revisions and scope.

The earlier local Eve runtimes and frozen relevance results remain available. Neither experiment currently establishes saved task time or lower cost. The Q8 asset and existing tags are unchanged.

## v0.1.1-rc.2: Preserved candidate and offline-start failure

This prerelease passed Windows/Linux CI and wheel installation, and its published marketplace plugin started online. Offline restart then failed on both platforms because uvx attempted to fetch the Git tag again. The patch pins an immutable package commit instead. The failed candidate tag remains unchanged, and the failure receipt is retained.

## v0.1.1-rc.1: Experimental runtime hardening

This candidate adds cache-only FP32 restart, one-command managed Q8 startup/shutdown, Windows child-process ownership, CPU dependency locking, configuration validation, and actionable startup diagnostics. Tests cover truncated provider responses, Windows credential-path casing, startup deadlines, interrupted startup, and authenticated shutdown.

The frozen public-source holdout contains nine questions and 54 candidate judgments after independent blind technical label review. Jev retained all 18 relevant passages and proposed 37.95% fewer evidence bytes. Eve FP32 and Q8 retained everything; no development prompt/threshold variant met the improvement gates, so Eve's policy stayed unchanged.

The matched Codex workflow failed usefulness: all ten answers were correct, but Jev retained every passage in that task and added 19.3% median end-to-end latency. Cache-aware API-equivalent cost was higher, with unequal observed cache hits. Filtering stays disabled, and this release makes no task-speedup or lower-bill claim.

Windows and Debian WSL2 clean-install, CLI, MCP transport, FP32/Q8 inference, shutdown, and offline-restart receipts are included. Candidate installed-plugin and remote CI gates are still pending at preparation. See [release validation](docs/release-validation.md) for exact status, evidence limits, and reproduction commands. The original Q8 model asset and its immutable v0.1.0 hash remain unchanged.

## v0.1.0: Local decision models and shadow evidence selection

This first experimental release includes a CLI, an MCP server, and a Codex plugin for comparing bounded relevance decisions. Backends include TypeSafe Jev, OpenRouter Jev, native local Eve FP32, and local Eve through llama.cpp.

The attached Q8_0 GGUF is converted from `anthonym21/qwen3-0.6b-rlcd-decision` revision `b327ec5efb5fdbf8bfafa3b369720ac5f6434b05`. It is 639442432 bytes and is distributed under Apache-2.0. The project code is MIT licensed. The conversion receipt records hashes and source provenance.

On 32 synthetic passages, Q8 changed no retention proposals or 0.5 classifications compared with the original FP32 checkpoint. Maximum absolute probability difference: 0.017433. The local checkpoint retained every passage at the conservative relevance threshold, so this release demonstrates local execution and probability comparison, not useful filtering by Eve or a Codex speedup.

Shadow mode preserves all evidence. Automatic filtering and automatic routing of built-in Codex tools are not enabled. See the README for installation and RESULTS.md for measured limitations.

Artifact SHA-256:

```text
49523f391d1408655b00b0c041a405efbb0ed343685f9415057cd6e04d8aac9a  eve-qwen3-0.6b-rlcd-q8_0.gguf
```
