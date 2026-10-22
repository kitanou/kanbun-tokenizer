"""Work-level robustness check: leave-one-work-out and multi-seed random splits (TPC spread)."""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
from pathlib import Path

from tokenizers import Tokenizer

from .manifest import assign_split, read_manifest, validate
from .train import train


def _lines(path: Path) -> list[str]:
    return [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _fit_eval(train_lines: list[str], eval_lines: list[str], vocab_size: int, workdir: Path) -> dict:
    corpus, tok = workdir / "train.txt", workdir / "tokenizer.json"
    corpus.write_text("\n".join(train_lines) + "\n", encoding="utf-8")
    train(corpus, tok, vocab_size, min_frequency=2)
    tokenizer = Tokenizer.from_file(str(tok))
    chars = sum(len(l) for l in eval_lines)
    tokens = sum(len(tokenizer.encode(l).ids) for l in eval_lines)
    exact = all(tokenizer.decode(tokenizer.encode(l).ids) == l for l in eval_lines)
    return {"characters": chars, "tokens": tokens, "tpc": tokens / chars, "exact_roundtrip": exact}


def _spread(values: list[float]) -> dict:
    return {
        "n": len(values), "mean": statistics.mean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values), "max": max(values), "median": statistics.median(values),
    }


def run(manifest: Path, root: Path, vocab_sizes: list[int], seeds: list[str], ratios=(0.8, 0.1, 0.1)) -> dict:
    rows = read_manifest(manifest)
    problems = validate(rows)
    if problems:
        raise SystemExit("\n".join(problems))
    docs = {r["work_id"]: _lines(root / r["local_path"]) for r in rows}
    result: dict = {"vocab_sizes": vocab_sizes, "lowo": {}, "seeds": {}}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for size in vocab_sizes:
            per_work = {}
            for held in list(docs):
                train_lines = [l for w, ls in docs.items() if w != held for l in ls]
                per_work[held] = _fit_eval(train_lines, docs[held], size, work)
            result["lowo"][size] = {"per_work": per_work, "tpc": _spread([v["tpc"] for v in per_work.values()]),
                                    "pooled_tpc": sum(v["tokens"] for v in per_work.values())
                                    / sum(v["characters"] for v in per_work.values())}
            by_seed = {}
            for seed in seeds:
                split = {w: assign_split(w, ratios, seed) for w in docs}
                tr = [l for w, ls in docs.items() if split[w] == "train" for l in ls]
                te = [l for w, ls in docs.items() if split[w] == "test" for l in ls]
                if not te or not tr:
                    by_seed[seed] = None
                    continue
                m = _fit_eval(tr, te, size, work)
                m["test_works"] = sorted(w for w in docs if split[w] == "test")
                by_seed[seed] = m
            ok = [v["tpc"] for v in by_seed.values() if v]
            result["seeds"][size] = {"per_seed": by_seed, "tpc": _spread(ok) if ok else None,
                                     "skipped_empty_test": sum(v is None for v in by_seed.values())}
    result["roundtrip_all_exact"] = all(
        v["exact_roundtrip"] for s in vocab_sizes for v in result["lowo"][s]["per_work"].values())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vocab-sizes", type=int, nargs="+", default=[2000, 8000, 16000])
    parser.add_argument("--seeds", nargs="+", default=[f"s{i}" for i in range(20)])
    args = parser.parse_args()
    res = run(args.manifest, args.root, args.vocab_sizes, args.seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for size in args.vocab_sizes:
        l, s = res["lowo"][size], res["seeds"][size]
        print(f"vocab {size}: LOWO mean {l['tpc']['mean']:.3f} sd {l['tpc']['stdev']:.3f} "
              f"[{l['tpc']['min']:.3f}, {l['tpc']['max']:.3f}] pooled {l['pooled_tpc']:.3f}")
        if s["tpc"]:
            print(f"        seeds mean {s['tpc']['mean']:.3f} sd {s['tpc']['stdev']:.3f} "
                  f"[{s['tpc']['min']:.3f}, {s['tpc']['max']:.3f}] n={s['tpc']['n']} skipped={s['skipped_empty_test']}")


if __name__ == "__main__":
    main()
