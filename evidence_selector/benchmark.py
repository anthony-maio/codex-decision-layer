"""Frozen relevance replay helpers. Never enables filtering in the plugin."""
from collections import Counter
import math
import re
import time

from .core import STOP, Candidate, QUESTION, evaluate_case, select, words
from .providers import DecisionError

PROMPTS = [QUESTION, "Does the passage help answer the query?",
           "Is the passage relevant to the query, even if it disproves it?"]


def bm25(query, candidates):
    docs = [Counter(w for w in re.findall(r"[a-z0-9]+", c.text.lower()) if w not in STOP) for c in candidates]
    lengths = [sum(d.values()) for d in docs]
    avg = sum(lengths) / len(docs) or 1
    scores = []
    for doc, length in zip(docs, lengths):
        score = 0
        for word in sorted(words(query)):
            df = sum(word in d for d in docs)
            freq = doc[word]
            score += math.log(1 + (len(docs) - df + .5) / (df + .5)) * freq * 2.5 / (freq + 1.5 * (.25 + .75 * length / avg))
        scores.append(score)
    order = sorted(range(len(candidates)), key=lambda i: (-scores[i], i))
    return {candidates[i].id for i in order[:3]}


def replay(data, method, provider=None, prompt_index=0, threshold=.1):
    rows = []
    class PromptProvider:
        name = provider.name if provider else "baseline"
        blocked = False
        def ask(self, state, question):
            if self.blocked:
                raise DecisionError("evaluation_circuit_open")
            try:
                return provider.ask(state, PROMPTS[prompt_index])
            except DecisionError as exc:
                if str(exc) in ("http_401", "http_402", "http_403", "http_429"):
                    self.blocked = True
                raise
    wrapped = PromptProvider() if provider else None
    for case in data["cases"]:
        candidates = [Candidate.parse(c) for c in case["candidates"]]
        tick = time.perf_counter()
        result = select(case["query"], candidates, wrapped, threshold)
        if method in ("retain-all", "bm25"):
            kept = {c.id for c in candidates} if method == "retain-all" else bm25(case["query"], candidates)
            result["proposed_keep_ids"] = [c.id for c in candidates if c.id in kept]
            result["proposed_drop_ids"] = [c.id for c in candidates if c.id not in kept]
            result["proposed_evidence_bytes"] = sum(len(c.text.encode()) for c in candidates if c.id in kept)
            for decision in result["decisions"]:
                decision.update(model=method, proposal="retain" if decision["id"] in kept else "drop", reason=method)
        result["latency_ms"] = (time.perf_counter() - tick) * 1000
        row = evaluate_case(case, result)
        row.update(repository=case["repository"], missed_contradiction_ids=sorted(set(case["contradiction_ids"]) - set(result["proposed_keep_ids"])))
        rows.append(row)
    return {"method": method, "prompt_index": prompt_index, "question": PROMPTS[prompt_index], "threshold": threshold,
            "mode": "shadow", "cases": rows, "summary": summarize(rows)}


def summarize(rows):
    relevant = sum(r["relevant"] for r in rows)
    missed = sum(len(r["missed_relevant_ids"]) for r in rows)
    before = sum(r["evidence_bytes"] for r in rows)
    after = sum(r["proposed_evidence_bytes"] for r in rows)
    summary = {"relevant": relevant, "missed_relevant": missed,
               "recall": 1 - missed / relevant if relevant else 1,
               "missed_critical": sum(len(r["missed_critical_ids"]) for r in rows),
               "missed_contradictions": sum(len(r["missed_contradiction_ids"]) for r in rows),
               "errors": sum(r["errors"] for r in rows), "byte_reduction": 1 - after / before,
               "selector_latency_ms": sum(r["latency_ms"] for r in rows),
               "retries": 0, "actual_evidence_bytes_removed": 0}
    groups = {name: [r for r in rows if r["repository"] == name] for name in sorted({r["repository"] for r in rows})}
    summary["repositories"] = {name: {"recall": sum(r["retained_relevant"] for r in group) / sum(r["relevant"] for r in group),
                                      "byte_reduction": 1 - sum(r["proposed_evidence_bytes"] for r in group) / sum(r["evidence_bytes"] for r in group)} for name, group in groups.items()}
    summary["gates"] = {"Q1": summary["recall"] >= .98 and summary["missed_critical"] == 0 and summary["missed_contradictions"] == 0 and all(g["recall"] >= .95 for g in summary["repositories"].values()),
                        "Q2": summary["errors"] == 0,
                        "U1": summary["byte_reduction"] >= .15 and all(g["byte_reduction"] >= .05 for g in summary["repositories"].values())}
    return summary
