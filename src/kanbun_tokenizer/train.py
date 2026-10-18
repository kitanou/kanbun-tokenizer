"""Train a reversible BPE baseline on one-text-per-line input."""
from __future__ import annotations

import argparse
from pathlib import Path

from tokenizers import Tokenizer, models, pre_tokenizers, trainers, normalizers, decoders


def train(input_path: Path, output_path: Path, vocab_size: int, min_frequency: int = 2) -> None:
    tokenizer = Tokenizer(models.BPE(unk_token="[UNK]"))
    # NFC is deliberately conservative; no simplified/traditional conversion.
    tokenizer.normalizer = normalizers.NFC()
    # Classical Chinese usually has no whitespace word boundaries. BPE learns
    # merges over character sequences; punctuation is kept available as text.
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size,
        min_frequency=min_frequency,
        special_tokens=["[UNK]"],
        show_progress=True,
    )
    tokenizer.train([str(input_path)], trainer)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tokenizer.save(str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="UTF-8 text file, one document/line")
    parser.add_argument("--output", type=Path, required=True, help="Output tokenizer.json path")
    parser.add_argument("--vocab-size", type=int, default=16000)
    parser.add_argument("--min-frequency", type=int, default=2)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"input file not found: {args.input}")
    train(args.input, args.output, args.vocab_size, args.min_frequency)


if __name__ == "__main__":
    main()
