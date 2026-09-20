# Sources and licenses

Project code is MIT licensed. Model weights are separate artifacts.

- [Eve RLCD](https://github.com/anthony-maio/eve-rlcd), by Anthony Maio, is MIT licensed. The local readout and prompt format follow its decision API. The reference comparison uses commit `ce5ebf627058b65acfc41d49e0e334a722a14ba5`.
- [The decision checkpoint](https://huggingface.co/anthonym21/qwen3-0.6b-rlcd-decision) is marked Apache-2.0 and derives from Qwen/Qwen3-0.6B-Base. The pinned revision is `b327ec5efb5fdbf8bfafa3b369720ac5f6434b05`. Quantized weights retain the model's license; they do not inherit this repository's MIT license.
- [llama.cpp](https://github.com/ggml-org/llama.cpp) is MIT licensed. Its converter and quantizer produce the optional GGUF artifacts. No llama.cpp binaries or source are vendored here.
- [TypeSafe](https://docs.typesafe.ai/) and [OpenRouter](https://openrouter.ai/docs/cookbook/building-agents/gate-tool-calls-with-jev) provide the hosted decision APIs. Using a hosted provider is subject to that provider's terms and charges.

This is an independent experimental integration, not an official OpenAI or TypeSafe product.
