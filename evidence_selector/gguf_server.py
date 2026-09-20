"""Expose GGUF letter probabilities through the same bounded decision endpoint."""
import argparse
import json
import math
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from http.server import HTTPServer

from .eve_server import handler_for
from .providers import NoRedirect


def render_noul(state, question):
    return (f"User: Context:\n{state.strip()}\n\nQuestion: {question.strip()}\nOptions:\n"
            "A) true\nB) false\nAnswer with the letter only.\nAssistant: The answer is")


class GgufBackend:
    def __init__(self, endpoint="http://127.0.0.1:8766", model="eve-q8_0", letter_ids=(362, 425)):
        url = urlsplit(endpoint)
        if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1") or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise ValueError("llama-server must be a loopback HTTP origin")
        self.endpoint, self.model = endpoint.rstrip("/"), model
        self.letter_ids = tuple(letter_ids)
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        for text, expected in zip((" A", " B"), self.letter_ids):
            if self.post("/tokenize", {"content": text, "add_special": False})["tokens"] != [expected]:
                raise ValueError("GGUF tokenizer does not match the decision letter IDs")

    def post(self, route, body):
        request = Request(self.endpoint + route, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with self.opener.open(request, timeout=60) as response:
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llama-endpoint", default="http://127.0.0.1:8766")
    parser.add_argument("--model", default="eve-q8_0")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    backend = GgufBackend(args.llama_endpoint, args.model)
    server = HTTPServer(("127.0.0.1", args.port), handler_for(backend))
    print(f"GGUF decisions ready at http://127.0.0.1:{args.port}/v1/systemone", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
