"""Describe how a trained tokenizer segments Classical Chinese function words (issue 04, descriptive only).

For every occurrence of a target string in held-out text this records whether it is
its own token ("isolated"), absorbed into a longer token ("merged"), or cut across
byte-level tokens ("split"). It measures segmentation, not syntax: a function word
being merged or isolated says nothing about whether the segmentation is linguistically good.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from tokenizers import Tokenizer

GROUPS = {
    "否定": list("不未無非弗勿毋"),
    "判断・句末": list("也矣焉耳哉"),
    "疑問・反語": list("乎耶邪歟豈何安孰"),
    "虚詞": list("之其而以於于者所則"),
    "連語": ["不亦", "未嘗", "何以", "然則", "是故", "無乃", "如何", "何如", "可以", "所以", "而已", "者也", "而已矣", "不可", "不能"],
}


def classify(tokenizer: Tokenizer, line: str, start: int, length: int) -> tuple[str, str]:
    """Return (class, covering token text) for line[start:start+length]."""
    enc = tokenizer.encode(line)
    end = start + length
    covering = [(a, b) for a, b in enc.offsets if a < end and b > start]
    if len(covering) == 1:
        a, b = covering[0]
        return ("isolated" if (a, b) == (start, end) else "merged"), line[a:b]
    spans = set(covering)
    if all(a >= start and b <= end for a, b in covering) and len(spans) < len(covering):
        return "split", line[start:end]  # a character cut into byte-level pieces
    return "straddle", "".join(line[a:b] for a, b in sorted(spans))  # target spans several tokens


def analyse(tokenizer_path: Path, lines: list[str]) -> dict:
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    out: dict = {}
    for group, targets in GROUPS.items():
        rows = {}
        for target in targets:
            counts, merged = Counter(), Counter()
            for line in lines:
                pos = line.find(target)
                while pos != -1:
                    cls, tok = classify(tokenizer, line, pos, len(target))
                    counts[cls] += 1
                    if cls in {"merged", "straddle"}:
                        merged[tok] += 1
                    pos = line.find(target, pos + 1)
            total = sum(counts.values())
            if total:
                rows[target] = {"n": total, **{k: counts[k] for k in ("isolated", "merged", "straddle", "split")},
                                "isolated_rate": counts["isolated"] / total,
                                "standalone_encoding_tokens": len(tokenizer.encode(target).ids),
                                "top_covering_tokens": merged.most_common(5)}
        out[group] = rows
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", type=Path, nargs="+", required=True)
    parser.add_argument("--input", type=Path, nargs="+", required=True, help="held-out text files, one document per line")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lines = [l for p in args.input for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    result = {"input_lines": len(lines), "input_characters": sum(len(l) for l in lines),
              "tokenizers": {str(t): analyse(t, lines) for t in args.tokenizer}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for t, groups in result["tokenizers"].items():
        print(t)
        for g, rows in groups.items():
            print(" ", g, " ".join(f"{k}:{v['n']}/{v['isolated_rate']:.2f}" for k, v in rows.items()))


if __name__ == "__main__":
    main()
