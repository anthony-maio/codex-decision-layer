"""Rebuild exact excerpts from pinned, licensed public sources; no model calls."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "public"
SOURCES = {
    "requests": ("psf/requests", "0e322af87745eff34caffe4df68456ebc20d9068", "Apache-2.0", "LICENSE"),
    "flask": ("pallets/flask", "ab8149664182b662453a563161aa89013c806dc9", "BSD-3-Clause", "LICENSE.txt"),
    "click": ("pallets/click", "934813e4d421071a1b3db3973c02fe2721359a6e", "BSD-3-Clause", "LICENSE.txt"),
}
# Same six passages per group, different question. No passage crosses splits.
GROUPS = [
    ("dev", "requests", "sessions.py", [(127,143),(282,300),(333,353),(61,88),(91,103),(750,779)], [
        ("Does Requests always remove Authorization on a same-host HTTP to HTTPS redirect using default ports?", [0,1], [0], [0], [2]),
        ("Which redirect responses change POST to GET, and does HEAD get changed?", [2], [2], [], [0]),
        ("How does merge_setting combine request and session dictionaries, including entries set to None?", [3], [3], [], [4]),
    ]),
    ("dev", "flask", "config.py", [(126,148),(152,170),(172,185),(304,321),(353,364),(218,228)], [
        ("Does from_prefixed_env reject a value when its JSON loader raises an exception?", [0,1,2], [1], [0,1], [3]),
        ("How do double underscores in a prefixed environment key create nested configuration dictionaries?", [0,1,2], [2], [], [4]),
        ("Does from_mapping load lowercase keys, and do keyword arguments override the mapping?", [3], [3], [3], [5]),
    ]),
    ("dev", "click", "types.py", [(594,613),(279,294),(643,665),(695,702),(875,886),(622,637)], [
        ("Which strings convert to boolean values, and are whitespace and case normalized?", [0], [0], [], [1]),
        ("Are files opened for reading lazy by default, including the special dash stream?", [2,3], [3], [2,3], [4]),
        ("Does a case-insensitive Choice return the original declared choice or its normalized spelling?", [1], [1], [], [0]),
    ]),
    ("holdout", "requests", "adapters.py", [(316,340),(560,576),(650,664),(536,544),(592,611),(667,679)], [
        ("Does a scalar HTTPAdapter timeout affect only connection establishment, and what happens to an invalid tuple?", [2,5], [2], [2], [3]),
        ("What does cert_verify configure for verify=False versus a CA bundle file or directory?", [0], [0], [], [4]),
        ("Does request_url send the full URL for HTTPS and SOCKS proxies as well as ordinary HTTP proxies?", [1,5], [1], [1], [4]),
    ]),
    ("holdout", "flask", "sessions.py", [(61,72),(237,245),(247,261),(336,348),(189,199),(361,383)], [
        ("Will modifying a nested dictionary inside SecureCookieSession automatically mark the session modified?", [0], [0], [0], [5]),
        ("What does open_session return for a bad cookie signature or when no signing serializer exists?", [3], [3], [], [4]),
        ("Can should_set_cookie refresh an unmodified permanent session, and which setting controls this?", [0,2,5], [0,2], [0,2], [1]),
    ]),
    ("holdout", "click", "parser.py", [(199,212),(357,371),(393,421),(463,480),(481,499),(328,344)], [
        ("Does option parsing continue after the double-dash separator?", [1,5], [1], [1], [2]),
        ("How does a long option process an explicit value, and what if that option takes no value?", [2,0,3,4], [2], [], [5]),
        ("When fewer arguments remain than an option requires, does _get_value_from_state always raise an error?", [3,4], [3], [3], [5]),
    ]),
]


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    datasets = {s: {"label_provenance": "Author labels adjudicated against independent blind technical review; not human-validated ground truth", "cases": []} for s in ("dev", "holdout")}
    provenance = {}
    for split, name, filename, spans, questions in GROUPS:
        repo, revision, license_id, license_file = SOURCES[name]
        source = f"src/{name}/{filename}"
        url = f"https://raw.githubusercontent.com/{repo}/{revision}/{source}"
        target = ROOT / "sources" / name / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(urllib.request.urlopen(url, timeout=30).read())
        raw = target.read_bytes()
        lines = raw.decode("utf-8").splitlines(keepends=True)
        license_path = ROOT / "licenses" / f"{name}.txt"
        license_path.parent.mkdir(exist_ok=True)
        if not license_path.exists():
            license_path.write_bytes(urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{revision}/{license_file}", timeout=30).read())
        provenance[f"{name}/{filename}"] = {"repository": f"https://github.com/{repo}", "revision": revision,
            "source": source, "url": url, "sha256": hashlib.sha256(raw).hexdigest(), "license": license_id,
            "license_sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(), "split": split}
        candidates = [{"id": f"{name}-{filename}-{a}-{b}", "source": f"{repo}@{revision}/{source}",
                       "start_line": a, "end_line": b, "text": "".join(lines[a-1:b])} for a,b in spans]
        for index, (query, relevant, critical, contradictions, hard_negatives) in enumerate(questions):
            ids = lambda positions: [candidates[i]["id"] for i in positions]
            datasets[split]["cases"].append({"id": f"{split}-{name}-{index+1}", "repository": name, "query": query,
                "candidates": candidates, "labels": {c["id"]: i in relevant for i,c in enumerate(candidates)},
                "critical_ids": ids(critical), "contradiction_ids": ids(contradictions), "hard_negative_ids": ids(hard_negatives)})
    for split, data in datasets.items():
        (ROOT / f"{split}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (ROOT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    review = [{k: c[k] for k in ("id", "query", "candidates")} for data in datasets.values() for c in data["cases"]]
    (ROOT / "review-input.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
