from pathlib import Path

from tokenizers import Tokenizer

from kanbun_tokenizer.evaluate import evaluate
from kanbun_tokenizer.train import train


def test_train_and_roundtrip(tmp_path: Path):
    source = tmp_path / "corpus.txt"
    source.write_text("學而時習之，不亦說乎。\\n知之為知之，不知為不知，是知也。\\n", encoding="utf-8")
    tokenizer_path = tmp_path / "tokenizer.json"
    train(source, tokenizer_path, vocab_size=128, min_frequency=1)
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    for text in source.read_text(encoding="utf-8").splitlines():
        assert tokenizer.decode(tokenizer.encode(text).ids) == text


def test_evaluation_report(tmp_path: Path):
    source = tmp_path / "corpus.txt"
    source.write_text("道可道，非常道。\\n", encoding="utf-8")
    tokenizer_path = tmp_path / "tokenizer.json"
    train(source, tokenizer_path, vocab_size=64, min_frequency=1)
    output = tmp_path / "evaluation.json"
    result = evaluate(tokenizer_path, source, output)
    assert output.exists()
    assert result["exact_roundtrip_rate"] == 1.0
    assert result["tokens_per_character"] is not None


def test_baseline_run(tmp_path: Path):
    from kanbun_tokenizer.baseline import run

    train_file = tmp_path / "train.txt"
    eval_file = tmp_path / "eval.txt"
    train_file.write_text("學而時習之，不亦說乎。\n知之為知之，不知為不知，是知也。\n", encoding="utf-8")
    eval_file.write_text("道可道，非常道。\n", encoding="utf-8")
    result = run(train_file, eval_file, tmp_path / "out", [300, 400], min_frequency=1, repeats=2)
    assert [r["method"] for r in result["runs"]] == ["char", "bpe", "bpe"]
    assert result["runs"][0]["tokens_per_character"] == 1.0
    assert all(r["exact_roundtrip_rate"] == 1.0 for r in result["runs"])
    assert result["dataset"]["eval"]["sha256"]
    assert (tmp_path / "out" / "baseline.json").exists()


def test_unseen_characters_roundtrip(tmp_path: Path):
    source = tmp_path / "corpus.txt"
    source.write_text("學而時習之\n", encoding="utf-8")
    tokenizer_path = tmp_path / "tokenizer.json"
    train(source, tokenizer_path, vocab_size=300, min_frequency=1)
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    text = "道可道，非常道。𠮷"
    assert tokenizer.decode(tokenizer.encode(text).ids) == text
