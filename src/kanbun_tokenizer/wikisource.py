"""Fetch chapter pages of works from zh.wikisource via the MediaWiki API, serially and politely.

Raw wikitext and the exact revision id (oldid) of every page are stored under
``<out>/<work>/``; nothing is converted or normalised here.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://zh.wikisource.org/w/api.php"
USER_AGENT = "kanbun-tokenizer/0.1 (personal research project; contact via GitHub user kitanou)"
DELAY_SECONDS = 1.5


def _get(params: dict, retries: int = 4) -> dict:
    query = urllib.parse.urlencode({**params, "format": "json", "formatversion": "2", "maxlag": "5"})
    delay = 5.0
    for _ in range(retries):
        req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
        except OSError:
            data = {"error": {"code": "network"}}
        finally:
            time.sleep(DELAY_SECONDS)
        if "error" not in data:
            return data
        if data["error"].get("code") not in {"maxlag", "ratelimited", "network"}:
            raise RuntimeError(data["error"])
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("API kept failing; stopping rather than hammering the server")


def list_subpages(work: str) -> list[str]:
    titles: list[str] = []
    params = {"action": "query", "list": "allpages", "apprefix": f"{work}/", "apnamespace": "0", "aplimit": "500", "apfilterredir": "nonredirects"}
    while True:
        data = _get(params)
        titles += [p["title"] for p in data["query"]["allpages"]]
        if "continue" not in data:
            return titles
        params = {**params, **data["continue"]}


def fetch_page(title: str) -> dict:
    data = _get({"action": "query", "prop": "revisions", "titles": title, "rvprop": "ids|timestamp|content",
                 "rvslots": "main"})
    page = data["query"]["pages"][0]
    rev = page["revisions"][0]
    return {"title": page["title"], "pageid": page["pageid"], "oldid": rev["revid"],
            "timestamp": rev["timestamp"], "wikitext": rev["slots"]["main"]["content"]}


def write_fetch_log(raw_root: Path, csv_path: Path) -> int:
    """Record title / oldid / timestamp / sha256 of every stored page (committable; raw files are not)."""
    import csv
    import hashlib

    rows = []
    for f in sorted(raw_root.glob("*/*.json")):
        page = json.loads(f.read_text(encoding="utf-8"))
        rows.append({
            "work": f.parent.name, "title": page["title"], "oldid": page["oldid"],
            "revision_timestamp": page["timestamp"],
            "wikitext_sha256": hashlib.sha256(page["wikitext"].encode("utf-8")).hexdigest(),
        })
    with csv_path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("works", nargs="*", help="top-level page titles whose subpages are fetched, e.g. 論語")
    parser.add_argument("--page", action="append", default=[], help="fetch one exact page title (stored as its own work)")
    parser.add_argument("--exclude", nargs="*", default=[], help="subpage names to skip, e.g. 全覽 序說")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fetch-log", type=Path, help="after fetching, write the oldid log CSV here")
    parser.add_argument("--list-only", action="store_true", help="print subpage titles and exit")
    args = parser.parse_args()
    for work in args.works:
        titles = [x for x in list_subpages(work) if x.split("/", 1)[1] not in args.exclude]
        if args.list_only:
            print(work, len(titles), titles)
            continue
        folder = args.out / work
        folder.mkdir(parents=True, exist_ok=True)
        for title in titles:
            target = folder / (title.split("/", 1)[1].replace("/", "_") + ".json")
            if target.exists():
                continue
            target.write_text(json.dumps(fetch_page(title), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(work, len(titles), "pages")
    for title in args.page:
        folder = args.out / title
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "page.json"
        if not target.exists():
            target.write_text(json.dumps(fetch_page(title), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(title, "1 page")
    if args.fetch_log:
        print("logged", write_fetch_log(args.out, args.fetch_log), "pages")


if __name__ == "__main__":
    main()
