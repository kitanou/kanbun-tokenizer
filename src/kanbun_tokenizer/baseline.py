"""Run character-level and BPE baselines with recorded provenance (issue 03)."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import tokenizers

from .evaluate import evaluate
from .train import train


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def environment() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "tokenizers": tokenizers.__version__,
    }


def _summary(samples: list[float]) -> dict:
    return {
        "median": statistics.median(samples),
        "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "samples": samples,
    }


def char_baseline(input_path: Path, repeats: int = 5) -> dict:
    """Character-level control: one token per NFC code point; TPC is 1.0 by definition."""
    texts = [
        unicodedata.normalize("NFC", line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    source_chars = sum(len(t) for t in texts)
    encode_times, decode_times = [], []
    for _ in range(repeats):
        start = time.perf_counter()
        encoded = [[ord(c) for c in t] for t in texts]
        encode_times.append(time.perf_counter() - start)
        start = time.perf_counter()
        decoded = ["".join(map(chr, ids)) for ids in encoded]
        decode_times.append(time.perf_counter() - start)
    exact = sum(a == b for a, b in zip(texts, decoded))
    return {
        "method": "char",
        "documents": len(texts),
        "source_characters": source_chars,
        "tokens": source_chars,
        "tokens_per_character": 1.0 if source_chars else None,
        "encode_seconds": _summary(encode_times),
        "decode_seconds": _summary(decode_times),
        "exact_roundtrip_rate": (exact / len(texts)) if texts else None,
    }


def run(train_path: Path, eval_path: Path, output_dir: Path, vocab_sizes: list[int],
        min_frequency: int = 2, repeats: int = 5) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs = [char_baseline(eval_path, repeats)]
    for size in vocab_sizes:
        tok_path = output_dir / f"bpe-{size}" / "tokenizer.json"
        train(train_path, tok_path, size, min_frequency)
        reports = [evaluate(tok_path, eval_path, output_dir / f"bpe-{size}" / "evaluation.json")
                   for _ in range(repeats)]
        first = reports[0]
        runs.append({
            "method": "bpe",
            "vocab_size": size,
            "documents": first["documents"],
            "source_characters": first["source_characters"],
            "tokens": first["tokens"],
            "tokens_per_character": first["tokens_per_character"],
            "encode_seconds": _summary([r["encode_seconds"] for r in reports]),
            "decode_seconds": _summary([r["decode_seconds"] for r in reports]),
            "exact_roundtrip_rate": first["exact_roundtrip_rate"],
        })
    result = {
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git_sha(),
        "environment": environment(),
        "config": {"vocab_sizes": vocab_sizes, "min_frequency": min_frequency,
                   "repeats": repeats, "normalizer": "NFC"},
        "dataset": {
            "train": {"path": str(train_path), "sha256": sha256_file(train_path)},
            "eval": {"path": str(eval_path), "sha256": sha256_file(eval_path)},
        },
        "runs": runs,
    }
    (output_dir / "baseline.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--eval", type=Path, required=True, help="held-out text (not the training file)")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--vocab-sizes", type=int, nargs="+", default=[16000, 32000, 64000])
    parser.add_argument("--min-frequency", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    for p in (args.train, args.eval):
        if not p.is_file():
            parser.error(f"file not found: {p}")
    if args.train.resolve() == args.eval.resolve():
        parser.error("--train and --eval must differ (held-out evaluation)")
    result = run(args.train, args.eval, args.output_dir, args.vocab_sizes,
                 args.min_frequency, args.repeats)
    for r in result["runs"]:
        print(r["method"], r.get("vocab_size", "-"), "TPC", r["tokens_per_character"],
              "roundtrip", r["exact_roundtrip_rate"])


if __name__ == "__main__":
    main()
