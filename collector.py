# collector.py
# Usage:
#   python collector.py \
#     --url https://www.ncaa.com/stats/volleyball-women/d1/current/individual/3 \
#     --out data/raw_blob.txt

import argparse
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib import robotparser

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

def allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        if rp.default_entry is None and not rp.entries:
            return True
        return rp.can_fetch(UA, url)
    except Exception:
        return True

def fetch_html(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def clean_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", default="data/raw_blob.txt")
    args = ap.parse_args()

    if not allowed_by_robots(args.url):
        raise SystemExit(f"robots.txt disallows scraping: {args.url}")

    html = fetch_html(args.url)
    blob = clean_visible_text(html)

    meta = (
        "=== RAW_BLOB METADATA ===\n"
        f"url: {args.url}\n"
        f"fetched_at_utc: {datetime.now(timezone.utc).isoformat()}\n"
        f"user_agent: {UA}\n"
        "=========================\n\n"
    )
    out_text = meta + blob

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out_text)
    print(f"Wrote {args.out} ({len(out_text):,} chars)")

if __name__ == "__main__":
    main()
