"""Evaluate token count, throughput, and exact round-trip recovery."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from tokenizers import Tokenizer


def evaluate(tokenizer_path: Path, input_path: Path, output_path: Path) -> dict:
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    texts = [line.rstrip("\n") for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    source_chars = sum(len(text) for text in texts)

    start = time.perf_counter()
    encodings = [tokenizer.encode(text) for text in texts]
    encode_seconds = time.perf_counter() - start

    token_count = sum(len(encoding.ids) for encoding in encodings)
    start = time.perf_counter()
    decoded = [tokenizer.decode(encoding.ids, skip_special_tokens=False) for encoding in encodings]
    decode_seconds = time.perf_counter() - start

    exact = sum(original == restored for original, restored in zip(texts, decoded))
    result = {
        "tokenizer": str(tokenizer_path),
        "input": str(input_path),
        "documents": len(texts),
        "source_characters": source_chars,
        "tokens": token_count,
        "tokens_per_character": (token_count / source_chars) if source_chars else None,
        "encode_seconds": encode_seconds,
        "encode_characters_per_second": (source_chars / encode_seconds) if encode_seconds else None,
        "decode_seconds": decode_seconds,
        "decode_characters_per_second": (source_chars / decode_seconds) if decode_seconds else None,
        "exact_roundtrip_documents": exact,
        "exact_roundtrip_rate": (exact / len(texts)) if texts else None,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.tokenizer, args.input, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
