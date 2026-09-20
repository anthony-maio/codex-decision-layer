"""Reconstruct the tied Qwen3 projection and create a reproducible Q8_0 GGUF."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--llama-cpp", required=True)
    parser.add_argument("--quantize", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    import torch
    from safetensors.torch import load_file, save_file
    from transformers import AutoTokenizer

    source, output = Path(args.source), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    record = json.loads((source / "decision.json").read_text())
    if record.get("format") != "rlcd-decision-only-v1" or not record.get("tied_embeddings"):
        raise ValueError("This converter requires a tied RLCD decision-only export")
    if record.get("model_type") != "qwen3" or record.get("prepend_bos"):
        raise ValueError("Only Qwen3 without an added BOS is supported")
    for name in ("model.safetensors", "decision_head.safetensors"):
        if sha256(source / name) != record["sha256"][name]:
            raise ValueError(f"Source hash mismatch: {name}")
    tensors = load_file(str(source / "model.safetensors"))
    head = load_file(str(source / "decision_head.safetensors"))
    embedding = tensors["embed_tokens.weight"]
    if "bias" in head or not torch.equal(embedding[record["letter_ids"]], head["weight"]):
        raise ValueError("Saved decision head differs from tied embedding rows; cannot reconstruct exactly")
    tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True)
    actual_ids = [tokenizer.encode(" " + letter, add_special_tokens=False) for letter in record["letters"]]
    if actual_ids != [[value] for value in record["letter_ids"]]:
        raise ValueError("Tokenizer letter IDs differ from the decision export")
    stage = output / "hf-reconstructed"
    stage.mkdir(exist_ok=True)
    # The converter expects CausalLM names; the export contains a bare model body.
    save_file({"model." + name: tensor for name, tensor in tensors.items()}, str(stage / "model.safetensors"))
    config = json.loads((source / "config.json").read_text())
    config["architectures"] = ["Qwen3ForCausalLM"]
    config["tie_word_embeddings"] = True
    (stage / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "added_tokens.json", "merges.txt", "vocab.json"):
        if (source / name).exists():
            shutil.copyfile(source / name, stage / name)
    f16 = output / "eve-qwen3-0.6b-rlcd-f16.gguf"
    q8 = output / "eve-qwen3-0.6b-rlcd-q8_0.gguf"
    subprocess.run([sys.executable, str(Path(args.llama_cpp) / "convert_hf_to_gguf.py"),
                    str(stage), "--outfile", str(f16), "--outtype", "f16"], check=True)
    subprocess.run([args.quantize, str(f16), str(q8), "Q8_0"], check=True)
    converter_revision = subprocess.check_output(["git", "-C", args.llama_cpp, "rev-parse", "HEAD"], text=True).strip()
    receipt = {"source_repo": "anthonym21/qwen3-0.6b-rlcd-decision", "source_revision": args.source_revision,
               "source_sha256": record["sha256"], "tied_head_exact_match": True,
               "letter_ids": record["letter_ids"], "prepend_bos": False,
               "converter_revision": converter_revision, "quantization": "Q8_0",
               "artifacts": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in (f16, q8)},
               "note": "GGUF reconstructs the tied vocabulary projection. Serve through the bounded-decision adapter; this file is not structurally decision-only."}
    (output / "conversion.json").write_text(json.dumps(receipt, indent=2) + "\n")
    shutil.copyfile(source / "decision.json", output / "decision.json")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
