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


def _row(work_id, text, root, **over):
    import hashlib
    (root / f"{work_id}.txt").write_text(text, encoding="utf-8")
    row = {
        "dataset_id": "d", "work_id": work_id, "title": work_id, "source_url": "https://example.org",
        "version": "v1", "downloaded_at": "2026-01-01",
        "sha256": hashlib.sha256(text.encode()).hexdigest(), "data_license": "CC0-1.0",
        "upstream_rights": "public domain", "attribution": "", "share_alike": "no",
        "redistribution_allowed": "yes", "training_allowed": "yes", "notes": "",
        "local_path": f"{work_id}.txt",
    }
    row.update(over)
    return row


def test_manifest_validation(tmp_path: Path):
    from kanbun_tokenizer.manifest import validate, verify_files

    good = _row("a", "學而\n", tmp_path)
    assert validate([good]) == [] and verify_files([good], tmp_path) == []
    bad = _row("b", "道\n", tmp_path, upstream_rights="unknown", training_allowed="unknown", sha256="xyz")
    problems = " ".join(validate([bad]))
    assert "unresolved" in problems and "training_allowed" in problems and "sha256" in problems
    dup = dict(good)
    assert any("duplicate" in p for p in validate([good, dup]))
    (tmp_path / "a.txt").write_text("changed\n", encoding="utf-8")
    assert verify_files([good], tmp_path)


def test_split_is_work_level_and_stable(tmp_path: Path):
    from kanbun_tokenizer.manifest import assign_split, write_splits

    rows = [_row(f"w{i}", f"文{i}\n", tmp_path) for i in range(40)]
    rec = write_splits(rows, tmp_path, tmp_path / "out")
    all_works = [w for ws in rec["works"].values() for w in ws]
    assert sorted(all_works) == sorted(r["work_id"] for r in rows)  # no work in two splits
    assert all(rec["works"][s] for s in ("train", "validation", "test"))
    assert assign_split("w3") == assign_split("w3")
    train_lines = (tmp_path / "out" / "train.txt").read_text(encoding="utf-8").splitlines()
    assert len(train_lines) == len(rec["works"]["train"])


def test_clean_org():
    from kanbun_tokenizer.kanripo import clean_org

    text = ("# -*- mode: mandoku-view -*-\n#+TITLE: 論語\n<pb:KR1h0004_CHANT_001-1a>¶\n** 1 《學而篇第一》\n\n"
            "1.1子曰：¶\n「學而時習之，¶\n不亦說乎？」<pb:X_002-1a>¶\n\n# src: LAO 1.1\n道可道，¶\n非恒道。\n")
    assert clean_org(text) == ["子曰：「學而時習之，不亦說乎？」", "道可道，非恒道。"]


def test_clean_wikitext():
    from kanbun_tokenizer.wikitext import clean_wikitext

    prose = ("{{header2\n| title = x\n}}\n<onlyinclude>\n"
             '<div id="a" style="b">\'\'\'一之一\'\'\'</div>\n'
             "子曰：「巧言令色，鮮{{另|矣|也}}仁。」-{zh-hans:后; zh-hant:後}-[[論語|學]]\n"
             "{{另2|《[[尚書|書]]》-{云}-，|注}}\n:commentary\n</onlyinclude>")
    assert clean_wikitext(prose, "prose") == ["子曰：「巧言令色，鮮矣仁。」後學", "《書》云，"]
    poem = "===x===\n<poem>\n:關關雎鳩，\n:在河之洲。\n</poem>\n=== 注釋 ===\n* note"
    assert clean_wikitext(poem, "poem") == ["關關雎鳩，在河之洲。"]
    plain = "==a==\n===木瓜===\n投我以木瓜。\n\n:《木瓜》，三章，章四句。\n===註解===\n瓊琚:玉"
    assert clean_wikitext(plain, "poem") == ["投我以木瓜。"]
    wang = "==一章==\n道可道，非常道，\n:{{*| 注}}\n名可名。"
    assert clean_wikitext(wang, "main-lines") == ["道可道，非常道，", "名可名。"]
