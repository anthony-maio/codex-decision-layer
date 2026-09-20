"""Loopback-only adapter for eve-rlcd's existing Decider, with no silent truncation."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class EveBackend:
    def __init__(self, checkpoint, device="cpu", model="eve-local"):
        from rlcd.decide import Decider, NoulQ, to_question
        from rlcd.schema import render_prefix, render_suffix

        self.decider = Decider.load(checkpoint, device=device)
        self.model = model
        self.noul = NoulQ
        self.to_question = to_question
        self.prefix = render_prefix
        self.suffix = render_suffix

    def decide(self, payload):
        if not isinstance(payload, dict) or payload.get("model") != self.model:
            raise ValueError("unknown_model")
        state, questions = payload.get("state"), payload.get("questions")
        if not isinstance(state, str) or not state.strip() or not isinstance(questions, dict) or not 1 <= len(questions) <= 8:
            raise ValueError("invalid_request")
        primitives, token_counts = [], []
        for key, question in questions.items():
            if not isinstance(key, str) or not isinstance(question, dict) or question.get("type") != "noul":
                raise ValueError("only_noul_supported")
            text = question.get("instructions")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("invalid_question")
            primitive = self.noul(text)
            q = self.to_question(state.strip(), primitive)
            suffix = self.suffix(q)
            encode = lambda s: self.decider.tok.encode(s, add_special_tokens=False)
            total = len(encode(self.prefix(state.strip()) + suffix)) + int(self.decider.policy.prepend_bos)
            # Refuse outside the documented training range instead of clipping evidence.
            if total > 512 or len(encode(suffix)) > 448 or len(encode(state.strip())) > 512:
                raise ValueError("prompt_exceeds_512_tokens")
            primitives.append(primitive)
            token_counts.append(total)
        answers = self.decider.ask(state, primitives, max_state_tokens=512, max_question_tokens=448)
        if len(answers) != len(primitives):
            raise ValueError("answer_count_mismatch")
        return {"model": self.model, "answers": {
            key: {"type": "noul", "noul": answer["p_true"]}
            for key, answer in zip(questions, answers)},
            "usage": {}, "diagnostics": {"full_prompt_tokens_per_question": token_counts,
                                          "truncated": False}}


def handler_for(backend):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path == "/health":
                self.send_json(200, {"status": "ok", "model": getattr(backend, "model", "unknown")})
            else:
                self.send_json(404, {"error": "not_found"})

        def send_json(self, status, value):
            raw = json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            if self.path != "/v1/systemone":
                self.send_json(404, {"error": "not_found"})
                return
            if self.headers.get("Origin") or self.headers.get_content_type() != "application/json":
                self.send_json(403, {"error": "non_browser_json_only"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 64_000:
                    self.send_json(413, {"error": "request_size"})
                    return
                self.connection.settimeout(10)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("incomplete_request")
                payload = json.loads(body)
                result = backend.decide(payload)
                self.send_json(200, result)
            except (ValueError, KeyError, TypeError, UnicodeError):
                self.send_json(422, {"error": "invalid_or_oversize_request"})
            except Exception:
                self.send_json(503, {"error": "inference_failed"})
    return Handler


def main():
    parser = argparse.ArgumentParser(description="Serve an existing Eve decision checkpoint on loopback")
    parser.add_argument("--checkpoint", default="anthonym21/qwen3-0.6b-rlcd-decision")
    parser.add_argument("--revision", default="b327ec5efb5fdbf8bfafa3b369720ac5f6434b05")
    parser.add_argument("--engine", choices=["native", "reference"], default="native")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--model", default="eve-local")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("threads must be positive")
    import torch
    torch.set_num_threads(args.threads)
    if args.engine == "reference":
        backend = EveBackend(args.checkpoint, args.device, args.model)
    else:
        from .hf_backend import HfBackend
        backend = HfBackend(args.checkpoint, args.device, args.model, args.revision)
    server = HTTPServer(("127.0.0.1", args.port), handler_for(backend))
    print(f"Eve ready at http://127.0.0.1:{args.port}/v1/systemone", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
