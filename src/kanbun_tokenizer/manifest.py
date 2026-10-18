"""Corpus manifest validation and work-level train/validation/test splitting (issue 02)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

COLUMNS = [
    "dataset_id", "work_id", "title", "source_url", "version", "downloaded_at", "sha256",
    "data_license", "upstream_rights", "attribution", "share_alike",
    "redistribution_allowed", "training_allowed", "notes", "local_path",
]
MANDATORY = [
    "dataset_id", "work_id", "title", "source_url", "version", "downloaded_at", "sha256",
    "data_license", "upstream_rights", "share_alike", "redistribution_allowed",
    "training_allowed", "local_path",
]
TRISTATE = ("share_alike", "redistribution_allowed", "training_allowed")
UNCLEAR = {"", "unknown", "未確認"}
# Problems that --allow-unverified-rights demotes to warnings (internal PoC only).
RIGHTS_MARKERS = ("unresolved", "training_allowed is not")
SPLITS = ("train", "validation", "test")


def read_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"manifest missing columns: {missing}")
        return list(reader)


def validate(rows: list[dict]) -> list[str]:
    """Return human-readable problems; an empty list means every row is adoptable."""
    problems: list[str] = []
    seen: dict[tuple, int] = {}
    hashes: dict[str, int] = {}
    for n, row in enumerate(rows, start=2):  # line 1 is the header
        where = f"row {n} ({row.get('dataset_id')}/{row.get('work_id')})"
        for col in MANDATORY:
            if not (row.get(col) or "").strip():
                problems.append(f"{where}: missing {col}")
        for col in TRISTATE:
            if (row.get(col) or "").strip().lower() not in {"yes", "no", "unknown"}:
                problems.append(f"{where}: {col} must be yes/no/unknown")
        sha = (row.get("sha256") or "").strip().lower()
        if sha and not re.fullmatch(r"[0-9a-f]{64}", sha):
            problems.append(f"{where}: sha256 is not 64 hex characters")
        for col in ("data_license", "upstream_rights"):
            if (row.get(col) or "").strip().lower() in UNCLEAR - {""}:
                problems.append(f"{where}: {col} unresolved; unclear rights block inclusion")
        if (row.get("training_allowed") or "").strip().lower() != "yes":
            problems.append(f"{where}: training_allowed is not 'yes'")
        if (row.get("share_alike") or "").strip().lower() == "yes" and not (row.get("attribution") or "").strip():
            problems.append(f"{where}: share-alike source requires attribution")
        key = (row.get("dataset_id"), row.get("work_id"))
        if key in seen:
            problems.append(f"{where}: duplicates row {seen[key]}")
        seen.setdefault(key, n)
        if sha:
            if sha in hashes:
                problems.append(f"{where}: same sha256 as row {hashes[sha]} (duplicate content)")
            hashes.setdefault(sha, n)
    return problems


def verify_files(rows: list[dict], root: Path) -> list[str]:
    problems = []
    for row in rows:
        p = root / row["local_path"]
        if not p.is_file():
            problems.append(f"{row['work_id']}: file not found: {p}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != row["sha256"].strip().lower():
            problems.append(f"{row['work_id']}: sha256 mismatch for {p}")
    return problems


def assign_split(work_id: str, ratios: tuple[float, float, float] = (0.8, 0.1, 0.1), seed: str = "kanbun-v1") -> str:
    """Deterministic work-level assignment: depends only on seed and work_id, so adding
    works never moves existing ones and one work can never straddle two splits."""
    digest = hashlib.sha256(f"{seed}:{work_id}".encode()).digest()
    x = int.from_bytes(digest[:8], "big") / 2**64
    if x < ratios[0]:
        return "train"
    return "validation" if x < ratios[0] + ratios[1] else "test"


def split_works(rows: list[dict], ratios=(0.8, 0.1, 0.1), seed: str = "kanbun-v1") -> dict[str, list[str]]:
    out: dict[str, list[str]] = {s: [] for s in SPLITS}
    for work_id in sorted({r["work_id"] for r in rows}):
        out[assign_split(work_id, ratios, seed)].append(work_id)
    return out


def write_splits(rows: list[dict], root: Path, output_dir: Path, ratios=(0.8, 0.1, 0.1), seed: str = "kanbun-v1",
                 release_eligible: bool = True) -> dict:
    """Write one-document-per-line split files and a splits.json recording membership."""
    splits = split_works(rows, ratios, seed)
    by_work: dict[str, list[dict]] = {}
    for r in rows:
        by_work.setdefault(r["work_id"], []).append(r)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, works in splits.items():
        with (output_dir / f"{name}.txt").open("w", encoding="utf-8") as f:
            for w in works:
                for r in by_work[w]:
                    for line in (root / r["local_path"]).read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            f.write(line + "\n")
    record = {"seed": seed, "ratios": list(ratios), "release_eligible": release_eligible, "works": splits}
    (output_dir / "splits.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="check manifest metadata (and files with --root)")
    v.add_argument("manifest", type=Path)
    v.add_argument("--root", type=Path, help="directory that local_path is relative to; also verifies SHA-256")
    s = sub.add_parser("split", help="validate, then write work-level train/validation/test files")
    s.add_argument("manifest", type=Path)
    s.add_argument("--root", type=Path, required=True)
    s.add_argument("--output-dir", type=Path, required=True)
    s.add_argument("--seed", default="kanbun-v1")
    s.add_argument("--allow-unverified-rights", action="store_true",
                   help="internal PoC only: rights problems become warnings and splits.json is marked release_eligible=false")
    args = parser.parse_args()
    rows = read_manifest(args.manifest)
    problems = validate(rows)
    if args.root:
        problems += verify_files(rows, args.root)
    waived = getattr(args, "allow_unverified_rights", False)
    if waived:
        warnings = [p for p in problems if any(m in p for m in RIGHTS_MARKERS)]
        problems = [p for p in problems if p not in warnings]
        for w in warnings:
            print("WARNING:", w)
    if problems:
        raise SystemExit("\n".join(problems))
    if args.cmd == "split":
        rec = write_splits(rows, args.root, args.output_dir, seed=args.seed, release_eligible=not waived)
        print({k: len(v) for k, v in rec["works"].items()})
    else:
        print(f"OK: {len(rows)} rows")


if __name__ == "__main__":
    main()
