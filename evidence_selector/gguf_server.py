"""Expose GGUF letter probabilities through the same bounded decision endpoint."""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from http.server import HTTPServer

from .eve_server import handler_for
from .providers import NoRedirect


def render_noul(state, question):
    return (f"User: Context:\n{state.strip()}\n\nQuestion: {question.strip()}\nOptions:\n"
            "A) true\nB) false\nAnswer with the letter only.\nAssistant: The answer is")


class GgufBackend:
    def __init__(self, endpoint="http://127.0.0.1:8766", model="eve-q8_0", letter_ids=(362, 425), deadline=None):
        url = urlsplit(endpoint)
        if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1") or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise ValueError("llama-server must be a loopback HTTP origin")
        self.endpoint, self.model = endpoint.rstrip("/"), model
        self.letter_ids = tuple(letter_ids)
        self.deadline = deadline
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        for text, expected in zip((" A", " B"), self.letter_ids):
            if self.post("/tokenize", {"content": text, "add_special": False})["tokens"] != [expected]:
                raise ValueError("GGUF tokenizer does not match the decision letter IDs")

    def post(self, route, body):
        request = Request(self.endpoint + route, json.dumps(body).encode(), {"Content-Type": "application/json"})
        timeout = 60 if self.deadline is None else min(60, self.deadline - time.monotonic())
        if timeout <= 0:
            raise TimeoutError("readiness deadline exceeded")
        with self.opener.open(request, timeout=timeout) as response:
            return json.load(response)

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
            tokens = self.post("/tokenize", {"content": prompt, "add_special": False, "parse_special": False})["tokens"]
            if len(tokens) > 512:
                raise ValueError("prompt_exceeds_512_tokens")
            prompts.append((key, tokens))
        answers, total_tokens = {}, 0
        for key, tokens in prompts:
            result = self.post("/completion", {
                "prompt": tokens, "n_predict": 1, "temperature": 1.0,
                "samplers": ["temperature"], "grammar": 'root ::= " A" | " B"',
                "n_probs": 10, "post_sampling_probs": True, "cache_prompt": False,
                "return_tokens": True, "seed": 1})
            # Grammar also permits a standalone space. Renormalize only the saved
            # A/B token IDs, exactly as the original decision head masks other rows.
            rows = result["completion_probabilities"][0]["top_probs"]
            probabilities = {row["id"]: row["prob"] for row in rows}
            yes, no = (probabilities[key] for key in self.letter_ids)
            if not all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in (yes, no)) or not 0 < yes + no <= 1.0001:
                raise ValueError("invalid_letter_probabilities")
            answers[key] = {"type": "noul", "noul": yes / (yes + no)}
            total_tokens += len(tokens)
        return {"model": self.model, "answers": answers,
                "usage": {"input_tokens": total_tokens, "output_tokens": len(answers)},
                "diagnostics": {"truncated": False, "readout": "renormalized_A_B", "cache_prompt": False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve Q8 decisions; optionally own a llama-server child")
    parser.add_argument("--llama-endpoint", default="http://127.0.0.1:8766")
    parser.add_argument("--model", default="eve-q8_0")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--llama-server", help="Executable to start and stop with this adapter")
    parser.add_argument("--gguf", help="Local Q8 file; required with --llama-server")
    parser.add_argument("--sha256", default="49523f391d1408655b00b0c041a405efbb0ed343685f9415057cd6e04d8aac9a")
    parser.add_argument("--gpu-layers", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=120)
    args = parser.parse_args(argv)
    if not math.isfinite(args.startup_timeout) or not 0 < args.startup_timeout <= 600:
        parser.error("startup-timeout must be between 0 and 600 seconds")
    if bool(args.llama_server) != bool(args.gguf):
        parser.error("--llama-server and --gguf must be supplied together")
    from .server_runtime import bind_server, serve, require_no_listener, install_stop_signal
    import signal
    previous = install_stop_signal()
    child = server = job = None
    try:
        server = bind_server(args.port)
        if args.llama_server:
            from .hf_backend import file_sha256
            url = urlsplit(args.llama_endpoint)
            if url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port or url.path not in ("", "/") or url.username or url.password or url.query or url.fragment:
                raise ValueError("Managed llama endpoint requires http://127.0.0.1:PORT")
            # Never adopt an existing listener as our owned child.
            require_no_listener(url.port)
            if file_sha256(args.gguf) != args.sha256:
                raise ValueError("GGUF hash mismatch")
            command = [args.llama_server, "-m", str(Path(args.gguf).resolve()), "-ngl", str(args.gpu_layers),
                       "--host", "127.0.0.1", "--port", str(url.port), "-c", "1024", "--parallel", "1", "--no-webui"]
            from .owned_process import ChildJob
            job = ChildJob()
            child = subprocess.Popen(command, stdout=sys.stderr, stderr=sys.stderr,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            job.attach(child)
        deadline = time.monotonic() + args.startup_timeout
        while True:
            if child is not None and child.poll() is not None:
                raise ValueError("llama-server exited before readiness")
            try:
                backend = GgufBackend(args.llama_endpoint, args.model, deadline=deadline)
                backend.deadline = None
                break
            except (OSError, ValueError):
                if time.monotonic() >= deadline:
                    raise ValueError("llama-server readiness timeout") from None
                time.sleep(0.2)
        serve(server, backend, "GGUF decisions")
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("Q8 startup failed. Check the adapter/llama ports, executable, GGUF SHA-256 and llama-server readiness. Use --llama-server PATH --gguf PATH for managed startup.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        signal.signal(signal.SIGTERM, previous)
        if server is not None:
            server.server_close()
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if job is not None:
            job.close()


if __name__ == "__main__":
    raise SystemExit(main())
