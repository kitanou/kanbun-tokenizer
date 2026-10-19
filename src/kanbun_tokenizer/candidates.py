"""Extract candidate sentences for the function-word / syntax evaluation set (issue 04).

Output is a JSONL of *unannotated* candidates with provenance. Labels, expected
behaviour and polysemy judgements are added by humans (see docs/annotation-guidelines.md);
nothing here decides what the correct segmentation is.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from .manifest import read_manifest

SENTENCE_END = "。？！"
CLAUSE_PUNCT = "，、；：。？！」』"

# phenomenon -> list of (pattern_id, regex). A match's whole span is the target; for
# single characters the span is that character. Patterns are surface forms only.
PHENOMENA: dict[str, list[tuple[str, str]]] = {
    "negation": [(c, c) for c in "不未無非"],
    "final_particle": [(c, c) for c in "也矣焉"],
    "question": [(c, c) for c in "乎耶邪歟豈"],
    "pattern": [
        ("不亦…乎", r"不亦[^。？！；，：]{1,8}乎"),
        ("何…之有", r"何[^。？！；，：]{0,6}之有"),
        ("豈…哉乎耶", r"豈[^。？！；，：]{1,12}[哉乎耶]"),
        ("如…何", r"如[^。？！；，：]{0,6}何"),
        ("無乃…乎", r"無乃[^。？！；，：]{0,10}乎"),
    ],
}


def sentences(paragraph: str) -> list[tuple[int, str]]:
    """Split on 。？！ keeping the punctuation; return (offset in paragraph, sentence)."""
    out, start = [], 0
    for i, ch in enumerate(paragraph):
        if ch in SENTENCE_END:
            out.append((start, paragraph[start:i + 1]))
            start = i + 1
    if start < len(paragraph):
        out.append((start, paragraph[start:]))
    return out


def _context_flags(sentence: str, start: int, end: int) -> dict:
    nxt = sentence[end] if end < len(sentence) else ""
    return {"clause_final": nxt == "" or nxt in CLAUSE_PUNCT,
            "sentence_initial": start == 0 or sentence[start - 1] in "「『"}


def find_matches(sentence: str) -> list[dict]:
    found = []
    for phenomenon, patterns in PHENOMENA.items():
        for pattern_id, regex in patterns:
            for m in re.finditer(regex, sentence):
                found.append({"phenomenon": phenomenon, "pattern": pattern_id,
                              "span": [m.start(), m.end()], "matched": m.group(0),
                              **_context_flags(sentence, m.start(), m.end())})
    return found


FUNCTIONS = {
    "negation": {"adverbial_negation", "existential_wu", "prohibitive", "copular_negation", "other"},
    "final_particle": {"final_particle", "non_final_use", "pronoun_or_locative", "other"},
    "question": {"interrogative_particle", "rhetorical", "preposition_or_other", "other"},
    "pattern": {"pattern_instance", "not_a_pattern", "other"},
}
EXPECTATIONS = {"separable", "unit", "no_expectation"}
STATUSES = {"candidate", "annotated", "audited", "rejected"}


def validate_record(rec: dict) -> list[str]:
    """Schema check for one JSONL record; returns problems (empty = valid)."""
    problems = []
    for key in ("id", "phenomenon", "pattern", "text", "span", "matched", "provenance", "status"):
        if key not in rec:
            problems.append(f"missing {key}")
    if problems:
        return problems
    start, end = rec["span"]
    if not (0 <= start < end <= len(rec["text"])) or rec["text"][start:end] != rec["matched"]:
        problems.append("span does not select 'matched' in text")
    if rec["phenomenon"] not in FUNCTIONS:
        problems.append(f"unknown phenomenon {rec['phenomenon']}")
    if rec["status"] not in STATUSES:
        problems.append(f"unknown status {rec['status']}")
    prov = rec["provenance"]
    for key in ("dataset_id", "work_id", "line", "source_sha256", "data_license"):
        if not prov.get(key):
            problems.append(f"provenance.{key} missing")
    ann = rec.get("annotation")
    if rec["status"] in {"annotated", "audited"}:
        if not ann:
            return problems + ["status requires annotation"]
        for key in ("function", "is_target_use", "expectation", "rationale", "annotator", "annotated_at", "ambiguity"):
            if ann.get(key) in (None, ""):
                problems.append(f"annotation.{key} missing")
        if ann.get("function") not in FUNCTIONS.get(rec["phenomenon"], set()):
            problems.append("annotation.function not allowed for this phenomenon")
        if ann.get("expectation") not in EXPECTATIONS:
            problems.append("annotation.expectation invalid")
        if ann.get("expectation") in {"separable", "unit"} and not ann.get("reference"):
            problems.append("a separable/unit expectation needs annotation.reference")
    if rec["status"] == "audited":
        audit = (ann or {}).get("audit") or {}
        if not audit.get("auditor") or audit.get("agrees") is None:
            problems.append("audited records need annotation.audit.auditor and .agrees")
    return problems


def _rank(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()


def _sources(path: Path) -> dict[int, tuple[str, str]]:
    if not path.is_file():
        return {}
    rows = path.read_text(encoding="utf-8").splitlines()[1:]
    return {int(a): (b, c) for a, b, c in (r.split("\t") for r in rows)}


def extract(manifest: Path, root: Path, splits: Path | None, per_pattern_per_work: int, per_pattern: int,
            min_len: int, max_len: int, seed: str, only_split: list[str] | None = None) -> list[dict]:
    split_of = {}
    if splits:
        for name, works in json.loads(splits.read_text(encoding="utf-8"))["works"].items():
            split_of.update({w: name for w in works})
    pool: dict[tuple[str, str], dict[str, list[dict]]] = {}
    for row in read_manifest(manifest):
        work = row["work_id"]
        if only_split and split_of.get(work, "unknown") not in only_split:
            continue
        text_path = root / row["local_path"]
        origin = _sources(text_path.with_suffix(".sources.tsv"))
        for line_no, paragraph in enumerate(text_path.read_text(encoding="utf-8").splitlines(), 1):
            for offset, sentence in sentences(paragraph):
                if not (min_len <= len(sentence) <= max_len):
                    continue
                for m in find_matches(sentence):
                    key = (m["phenomenon"], m["pattern"])
                    page, oldid = origin.get(line_no, ("", ""))
                    cid = hashlib.sha1(f"{work}|{line_no}|{offset}|{m['pattern']}|{m['span'][0]}".encode()).hexdigest()[:12]
                    cand = {
                        "id": cid, "phenomenon": m["phenomenon"], "pattern": m["pattern"], "text": sentence,
                        "span": m["span"], "matched": m["matched"],
                        "context": {"clause_final": m["clause_final"], "sentence_initial": m["sentence_initial"]},
                        "provenance": {"dataset_id": row["dataset_id"], "work_id": work, "line": line_no,
                                       "sentence_offset": offset, "page_title": page, "oldid": oldid,
                                       "source_sha256": row["sha256"], "data_license": row["data_license"]},
                        "corpus_split": split_of.get(work, "unknown"),
                        "status": "candidate", "annotation": None,
                    }
                    pool.setdefault(key, {}).setdefault(work, []).append(cand)
    chosen: list[dict] = []
    for key in sorted(pool):
        picked: list[dict] = []
        for work in sorted(pool[key]):
            cands = sorted(pool[key][work], key=lambda c: _rank(seed, c["id"]))
            # spread over clause positions: alternate clause-final / non-final when both exist
            finals = [c for c in cands if c["context"]["clause_final"]]
            others = [c for c in cands if not c["context"]["clause_final"]]
            mixed = [c for pair in zip(finals, others) for c in pair] + finals[len(others):] + others[len(finals):]
            picked += mixed[:per_pattern_per_work]
        picked.sort(key=lambda c: _rank(seed, "final", c["id"]))
        chosen += picked[:per_pattern]
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--splits", type=Path, help="splits.json; adds corpus_split to every candidate")
    parser.add_argument("--only-split", nargs="+", choices=["train", "validation", "test", "unknown"],
                        help="draw candidates only from works in these corpus splits (needs --splits)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--per-pattern-per-work", type=int, default=3)
    parser.add_argument("--per-pattern", type=int, default=30)
    parser.add_argument("--min-len", type=int, default=8)
    parser.add_argument("--max-len", type=int, default=60)
    parser.add_argument("--seed", default="kanbun-eval-v1")
    parser.add_argument("--validate", type=Path, help="validate an annotated JSONL file and exit")
    args = parser.parse_args()
    if args.validate:
        bad = 0
        for n, line in enumerate(args.validate.read_text(encoding="utf-8").splitlines(), 1):
            for problem in validate_record(json.loads(line)):
                bad += 1
                print(f"line {n}: {problem}")
        raise SystemExit(1 if bad else 0)
    if not (args.manifest and args.root and args.output):
        parser.error("--manifest, --root and --output are required unless --validate is used")
    cands = extract(args.manifest, args.root, args.splits, args.per_pattern_per_work, args.per_pattern,
                    args.min_len, args.max_len, args.seed, args.only_split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for c in cands:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    by = {}
    for c in cands:
        by.setdefault(c["pattern"], []).append(c["corpus_split"])
    for k, v in by.items():
        print(k, len(v), {s: v.count(s) for s in sorted(set(v))})


if __name__ == "__main__":
    main()
