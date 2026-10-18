"""Convert Kanripo (mandoku/org) text files into one-paragraph-per-line text and a manifest."""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
import unicodedata
from datetime import date
from pathlib import Path

from .manifest import COLUMNS

_TAG = re.compile(r"<[^>\n]*>")
_VERSE_NO = re.compile(r"^\d+(?:\.\d+)*(?=[^\d.\s])")
_NEWLINE_MARK = "¶"


def clean_org(text: str) -> list[str]:
    """Return paragraphs (one per output line). Drops org headers, comments, page
    markers, verse numbers and pilcrows; keeps punctuation and character forms as-is
    (apart from NFC, which the tokenizer applies anyway)."""
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append("".join(current))
            current.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith(("#", "*", ":")):  # org header/comment/heading/property
            flush()
            continue
        line = _TAG.sub("", line).replace(_NEWLINE_MARK, "")
        line = _VERSE_NO.sub("", line).strip()
        if line:
            current.append(unicodedata.normalize("NFC", line))
    flush()
    return paragraphs


# Rights notes per Kanripo base edition. Findings, not legal conclusions; see docs/data-policy.md.
EDITION_RIGHTS = {
    "CHANT": (
        "restricted: CHANT (CUHK) licence reportedly bars derivative works without prior written "
        "CUHK approval; full agreement not read",
        "no",
    ),
    "tls": ("unknown: no licence/terms found for the TLS (Thesaurus Linguae Sericae) edition", "unknown"),
}


def _meta(repo: Path) -> dict:
    first = next(iter(sorted(repo.glob("*_001.txt"))), None)
    props: dict[str, str] = {}
    if first:
        for line in first.read_text(encoding="utf-8").splitlines()[:20]:
            m = re.match(r"#\+(TITLE|PROPERTY): ?(\w+)? ?(.*)", line)
            if m and m.group(1) == "TITLE":
                props["title"] = (m.group(2) or "") + (m.group(3) or "")
            elif m and m.group(2) == "BASEEDITION":
                props.setdefault("baseedition", m.group(3).strip())
    return props


def build(raw_root: Path, out_dir: Path, manifest_path: Path, download_date: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for repo in sorted(p for p in raw_root.iterdir() if (p / ".git").exists()):
        work_id = repo.name
        paragraphs: list[str] = []
        for f in sorted(repo.glob(f"{work_id}_*.txt")):
            paragraphs += clean_org(f.read_text(encoding="utf-8"))
        data = ("\n".join(paragraphs) + "\n").encode("utf-8")
        (out_dir / f"{work_id}.txt").write_bytes(data)
        meta = _meta(repo)
        sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        edition = meta.get("baseedition", "unknown")
        rows.append({
            "dataset_id": "kanripo", "work_id": work_id, "title": meta.get("title", work_id),
            "source_url": f"https://github.com/kanripo/{work_id}", "version": sha,
            "downloaded_at": download_date, "sha256": hashlib.sha256(data).hexdigest(),
            "data_license": "CC-BY-SA-4.0 (stated at github.com/kanripo org level; no per-repo LICENSE)",
            "upstream_rights": EDITION_RIGHTS.get(edition, ("unknown", "unknown"))[0],
            "attribution": "Kanseki Repository (kanripo.org); base edition: " + edition,
            "share_alike": "yes", "redistribution_allowed": "unknown", "training_allowed": EDITION_RIGHTS.get(edition, ("unknown", "unknown"))[1],
            "notes": f"Traditional characters. Base edition '{edition}' rights not verified. "
                     "sha256 is of the cleaned file (see kanripo.clean_org); raw commit in version.",
            "local_path": f"{work_id}.txt",
        })
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True, help="directory containing cloned kanripo repos")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--downloaded-at", default=date.today().isoformat())
    args = parser.parse_args()
    print(f"{build(args.raw_root, args.out_dir, args.manifest, args.downloaded_at)} works")


if __name__ == "__main__":
    main()
