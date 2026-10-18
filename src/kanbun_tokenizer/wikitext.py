"""Turn zh.wikisource wikitext into plain text paragraphs and build the corpus manifest.

Only the base text is kept: headers, navigation, anchors, commentary, footnotes and
templates are dropped. Character forms are left exactly as written (no 繁簡/異体字
conversion); language-converter markup keeps the traditional (zh-hant) variant.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from .manifest import COLUMNS

_CONVERT = re.compile(r"-\{(.*?)\}-", re.DOTALL)
_HANT = re.compile(r"zh-hant:\s*([^;}]*)")
_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_FILE = re.compile(r"\[\[(?:File|Image|文件|檔案|图像|圖像):[^\]]*\]\]", re.IGNORECASE)
_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_REF = re.compile(r"<ref[^>]*?(?:/>|>.*?</ref>)", re.DOTALL)


COMMENTARY_HEADINGS = {"註解", "註釋", "注釋", "毛詩序", "魯詩說", "齊詩說", "齐诗说", "韓詩說", "三家詩說"}
_FOOTER = re.compile(r"^《[^》]*》[，,].*章")
_ANCHOR_LINE = re.compile(r"^<div id=[^>]*>.*</div>\s*$")


def _convert(m: re.Match) -> str:
    body = m.group(1)
    hant = _HANT.search(body)
    return hant.group(1).strip() if hant else body


def _split_top(body: str) -> list[str]:
    """Split on '|' that is not inside [[...]] or {{...}}."""
    parts, depth, cur, i = [], 0, [], 0
    while i < len(body):
        two = body[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1
            cur.append(two)
            i += 2
        elif two in ("]]", "}}") and depth:
            depth -= 1
            cur.append(two)
            i += 2
        elif body[i] == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(body[i])
            i += 1
    parts.append("".join(cur))
    return parts


def _drop_templates(text: str) -> str:
    """Expand {{另|main|variant}} to its first argument; remove every other template (nesting-aware)."""
    out, i = [], 0
    while i < len(text):
        if not text.startswith("{{", i):
            out.append(text[i])
            i += 1
            continue
        depth, j = 0, i
        while j < len(text):
            if text.startswith("{{", j):
                depth += 1
                j += 2
            elif text.startswith("}}", j):
                depth -= 1
                j += 2
                if depth == 0:
                    break
            else:
                j += 1
        parts = _split_top(text[i + 2:j - 2] if depth == 0 else "")
        if depth == 0 and parts[0].strip() in {"另", "另2"} and len(parts) > 1:
            out.append(_inline(parts[1]))
        i = j
    return "".join(out)


def _inline(text: str) -> str:
    text = _COMMENT.sub("", text)
    text = _REF.sub("", text)
    text = _CONVERT.sub(_convert, text)
    text = _drop_templates(text)
    text = _FILE.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _TAG.sub("", text)
    return text.replace("'''", "").replace("''", "")


def _only_include(text: str) -> str:
    m = re.search(r"<onlyinclude>(.*?)</onlyinclude>", text, re.DOTALL)
    return m.group(1) if m else text


def clean_wikitext(text: str, mode: str) -> list[str]:
    """mode: 'prose' (論語/孟子), 'poem' (詩經: <poem> blocks), 'main-lines' (drop ':' commentary lines)."""
    text = re.sub(r"\{\|.*?\|\}", "", text, flags=re.DOTALL)  # wikitables (e.g. a poem laid out as a table) are dropped
    if mode == "poem":
        blocks = re.findall(r"<poem[^>]*>(.*?)</poem>", _only_include(text), re.DOTALL)
        if not blocks:  # pages without <poem>: colon-indented lines outside commentary sections
            colon, plain, heading, level = [], [], "", 0
            for raw in _COMMENT.sub("", text).splitlines():
                line = raw.strip()
                m = re.match(r"(=+)\s*(.*?)\s*=+\s*$", line)
                if m:
                    heading, level = _inline(m.group(2)).strip(), len(m.group(1))
                    continue
                if not line or heading in COMMENTARY_HEADINGS or _FOOTER.match(line.lstrip(":").strip()):
                    continue
                if line.startswith(":"):
                    colon.append(line)
                elif level == 3 and not line.startswith(("毛詩序", "{{", "<", "__")):
                    plain.append(line)
            current = colon or plain  # pages use either ':' lines or plain lines under the poem heading
            blocks = ["\n".join(current)] if current else []
        paragraphs = []
        for block in blocks:
            lines = [_inline(l).strip(" :　\t") for l in block.splitlines()]
            joined = "".join(l for l in lines if l)
            if joined:
                paragraphs.append(joined)
        return [unicodedata.normalize("NFC", p) for p in paragraphs]
    body = _only_include(text) if mode == "prose" else text
    body = _COMMENT.sub("", body)
    lines = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(("=", "*", "#", "{|", "|", "!", "}")) or _ANCHOR_LINE.match(line):
            continue
        if mode == "main-lines" and line.startswith(":"):
            continue
        if mode == "prose" and line.startswith(":"):
            continue
        cleaned = _inline(line).strip(" 　\t")
        if cleaned:
            lines.append(unicodedata.normalize("NFC", cleaned))
    return lines


WORKS = {  # work directory -> (work_id, cleaning mode)
    "論語": ("zhws-lunyu", "prose"),
    "孟子": ("zhws-mengzi", "prose"),
    "詩經": ("zhws-shijing", "poem"),
    "道德經 (王弼本)": ("zhws-daodejing-wangbi", "main-lines"),
}


def build(raw_root: Path, out_dir: Path, manifest_path: Path, fetch_date: str) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, report = [], []
    for folder, (work_id, mode) in WORKS.items():
        pages = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((raw_root / folder).glob("*.json"))]
        paragraphs, empty, pd_old = [], [], 0
        for page in pages:
            got = clean_wikitext(page["wikitext"], mode)
            if not got:
                empty.append(page["title"])
            paragraphs += got
            pd_old += bool(re.search(r"\{\{\s*PD-old", page["wikitext"], re.IGNORECASE))
        data = ("\n".join(paragraphs) + "\n").encode("utf-8")
        (out_dir / f"{work_id}.txt").write_bytes(data)
        title = folder.split(" ")[0]
        rows.append({
            "dataset_id": "zh-wikisource", "work_id": work_id, "title": title,
            "source_url": f"https://zh.wikisource.org/wiki/{folder}",
            "version": f"{len(pages)} pages at fixed oldids, see data/wikisource-fetch-log.csv",
            "downloaded_at": fetch_date, "sha256": hashlib.sha256(data).hexdigest(),
            "data_license": "CC-BY-SA-4.0 and GFDL (Chinese Wikisource contributions)",
            "upstream_rights": f"ancient text, author deceased >1000y; PD-old template on {pd_old}/{len(pages)} pages",
            "attribution": "Chinese Wikisource contributors (page histories at zh.wikisource.org); revisions in fetch log",
            "share_alike": "yes", "redistribution_allowed": "yes", "training_allowed": "yes",
            "notes": f"Cleaned with wikitext.clean_wikitext(mode={mode}); {len(paragraphs)} paragraphs; "
                     f"pages with no extracted text: {len(empty)}. Effect of ShareAlike on trained artifacts not reviewed.",
            "local_path": f"{work_id}.txt",
        })
        report.append((work_id, len(pages), len(paragraphs), len(data.decode().replace("\n", "")), empty[:5], len(empty)))
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    for r in report:
        print(r)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fetched-at", required=True)
    args = parser.parse_args()
    build(args.raw_root, args.out_dir, args.manifest, args.fetched_at)


if __name__ == "__main__":
    main()
