"""Small, explicit HTTP adapters. No automatic retries or remote fallback."""
from __future__ import annotations

import json
import http.client
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class DecisionError(Exception):
    """A provider could not supply a valid decision; retain the evidence."""


def probability(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise DecisionError("invalid_probability")
    return float(value)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DecisionError("redirect_refused")


@dataclass
class Answer:
    probability: float
    model: str
    usage: dict


class HttpProvider:
    def __init__(self, provider, endpoint=None, key_env=None, model=None, timeout=15.0, require_key=True):
        if provider not in ("typesafe", "openrouter", "eve"):
            raise ValueError("Unknown provider")
        if not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("timeout must be between 0 and 120 seconds")
        self.name = provider
        self.timeout = timeout
        self.model = model or {"typesafe": "jev-1.13.0", "openrouter": "typesafe/jev-1.13", "eve": "eve-local"}[provider]
        defaults = {"typesafe": "https://api.typesafe.ai/v1/systemone",
                    "openrouter": "https://openrouter.ai/api/alpha/decisions",
                    "eve": "http://127.0.0.1:8765/v1/systemone"}
        self.endpoint = endpoint or defaults[provider]
        url = urllib.parse.urlsplit(self.endpoint)
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Endpoint must not contain credentials, query, or fragment")
        if provider == "eve":
            if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1"):
                raise ValueError("Eve endpoint must be HTTP on a loopback address")
        elif self.endpoint != defaults[provider]:
            raise ValueError("Hosted providers use their fixed official endpoint")
        self.key = None
        if provider != "eve":
            name = key_env or {"typesafe": "TYPESAFE_API_KEY", "openrouter": "OPENROUTER_API_KEY"}[provider]
            self.key = os.environ.get(name)
            if not self.key and require_key:
                raise ValueError(f"Missing API key environment variable: {name}")
        # Explicit local requests must not pass through an environment HTTP proxy.
        handlers = [NoRedirect()]
        if provider == "eve":
            handlers.append(urllib.request.ProxyHandler({}))
        self.opener = urllib.request.build_opener(*handlers)

    def ask(self, state, question):
        body = {"model": self.model, "state": state,
                "questions": {"relevant": {"type": "noul", "instructions": question}}}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        request = urllib.request.Request(self.endpoint, json.dumps(body).encode(), headers, method="POST")
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise DecisionError("response_too_large")
            result = json.loads(raw)
            answer = result["answers"]["relevant"]
            if answer["type"] != "noul":
                raise DecisionError("wrong_answer_type")
            p = probability(answer["noul"])
            actual_model = result.get("model")
            if not isinstance(actual_model, str) or not actual_model:
                raise DecisionError("missing_model_identity")
            usage = result.get("usage", {})
            if not isinstance(usage, dict):
                raise DecisionError("invalid_usage")
            # Do not retain arbitrary response strings that may echo evidence or credentials.
            safe_usage = {}
            for name in ("input_tokens", "output_tokens", "cost", "prompt_tokens", "total_tokens"):
                value = usage.get(name)
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    safe_usage[name] = value
            return Answer(p, actual_model, safe_usage)
        except urllib.error.HTTPError as exc:
            # Provider error bodies can contain submitted text. Never log them.
            raise DecisionError(f"http_{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
            raise DecisionError("connection_failed") from None
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise DecisionError("invalid_response") from None
