"""Minimal local inference for the published decision-only export."""
import hashlib
import json
from pathlib import Path

from .gguf_server import render_noul

MODEL_REPO = "anthonym21/qwen3-0.6b-rlcd-decision"
MODEL_REVISION = "b327ec5efb5fdbf8bfafa3b369720ac5f6434b05"


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class HfBackend:
    def __init__(self, checkpoint=MODEL_REPO, device="cpu", model="eve-local", revision=MODEL_REVISION, offline=False):
        import torch
        from huggingface_hub import snapshot_download
        from safetensors.torch import load_file
        from transformers import AutoModel, AutoTokenizer

        if not Path(checkpoint).is_dir():
            if checkpoint != MODEL_REPO:
                raise ValueError("Use a local checkpoint directory or the documented model repository")
            checkpoint = snapshot_download(checkpoint, revision=revision, local_files_only=offline)
        source = Path(checkpoint)
        record = json.loads((source / "decision.json").read_text())
        if record.get("format") != "rlcd-decision-only-v1" or record.get("model_type") != "qwen3" or record.get("prepend_bos"):
            raise ValueError("Expected a Qwen3 decision-only export without BOS")
        for name in ("model.safetensors", "decision_head.safetensors"):
            if file_sha256(source / name) != record["sha256"][name]:
                raise ValueError(f"Checkpoint hash mismatch: {name}")
        self.tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True, trust_remote_code=False)
        if [self.tokenizer.encode(" " + letter, add_special_tokens=False) for letter in record["letters"]] != [[i] for i in record["letter_ids"]]:
            raise ValueError("Decision letter IDs do not match the tokenizer")
        self.body = AutoModel.from_pretrained(source, local_files_only=True, trust_remote_code=False,
                                             dtype=torch.float32, attn_implementation="eager").to(device).eval()
        head = load_file(str(source / "decision_head.safetensors"))
        if head["weight"].shape != (26, self.body.config.hidden_size):
            raise ValueError("Invalid decision head shape")
        self.weight = head["weight"].to(device)
        self.bias = head.get("bias")
        if self.bias is not None:
            self.bias = self.bias.to(device)
        self.model, self.device, self.torch = model, device, torch

    def decide(self, payload):
        if not isinstance(payload, dict) or payload.get("model") != self.model:
            raise ValueError("unknown_model")
        state, questions = payload.get("state"), payload.get("questions")
        if not isinstance(state, str) or not state.strip() or not isinstance(questions, dict) or not 1 <= len(questions) <= 8:
            raise ValueError("invalid_request")
        prompts = []
        for key, question in questions.items():
            if not isinstance(question, dict) or question.get("type") != "noul" or not isinstance(question.get("instructions"), str) or not question["instructions"].strip():
                raise ValueError("only_noul_supported")
            prompt = render_noul(state, question["instructions"])
            tokens = self.tokenizer.encode(prompt, add_special_tokens=False)
            if len(tokens) > 512:
                raise ValueError("prompt_exceeds_512_tokens")
            prompts.append((key, tokens))
        answers, total = {}, 0
        with self.torch.inference_mode():
            for key, tokens in prompts:
                ids = self.torch.tensor([tokens], device=self.device)
                hidden = self.body(input_ids=ids, use_cache=False).last_hidden_state[0, -1].float()
                logits = self.torch.nn.functional.linear(hidden, self.weight[:2], None if self.bias is None else self.bias[:2])
                p = self.torch.softmax(logits, dim=-1)[0].item()
                answers[key] = {"type": "noul", "noul": p}
                total += len(tokens)
        return {"model": self.model, "answers": answers, "usage": {"input_tokens": total, "output_tokens": 0},
                "diagnostics": {"truncated": False, "readout": "saved_fp32_decision_head"}}
