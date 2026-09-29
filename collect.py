#!/usr/bin/env python3
"""Collect GitHub's weekly trending repositories into a Markdown digest.

Fetches https://github.com/trending?since=weekly, writes
data/<ISO week>.json and digests/<ISO week>.md, and refreshes the
digest index in README.md. Standard library only.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

TRENDING_URL = "https://github.com/trending?since=weekly"
ROOT = Path(__file__).resolve().parent
INDEX_START = "<!-- digests:start -->"
INDEX_END = "<!-- digests:end -->"

_ARTICLE_RE = re.compile(r"<article\b[^>]*\bBox-row\b[^>]*>(.*?)</article>", re.S | re.I)
_REPO_RE = re.compile(r'<h2\b[^>]*>.*?href="/([^"/]+)/([^"/?#]+)"', re.S | re.I)
_DESCRIPTION_RE = re.compile(r"</h2>.*?<p\b[^>]*>(.*?)</p>", re.S | re.I)
_LANGUAGE_RE = re.compile(r'itemprop="programmingLanguage"[^>]*>(.*?)<', re.S | re.I)
_BUILT_BY_RE = re.compile(r"Built by(.*?)</span>", re.S | re.I)
_AVATAR_RE = re.compile(r'alt="@([^"]+)"')
_STARS_THIS_WEEK_RE = re.compile(r"(\d[\d,]*)\s+stars?\s+this week", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_NUMBER_RE = re.compile(r"\d[\d,]*")


def fetch(url: str, attempts: int = 3) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "trending-digest (+https://github.com/yentelie/trending-digest)",
            "Accept": "text/html",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset)
        except OSError as error:  # URLError and HTTPError are OSError subclasses
            if attempt == attempts:
                raise
            print(f"fetch failed ({error}); retrying", file=sys.stderr)
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", fragment))).strip()


def _count(fragment: str | None) -> int | None:
    if fragment is None:
        return None
    match = _NUMBER_RE.search(_text(fragment))
    return int(match.group().replace(",", "")) if match else None


def parse_trending(page: str) -> list[dict]:
    """Parse the trending page HTML into one dict per repository, in page order."""
    repos = []
    for article in _ARTICLE_RE.findall(page):
        repo = _REPO_RE.search(article)
        if not repo:
            continue
        owner, name = repo.groups()
        path = re.escape(f"/{owner}/{name}")
        stars = re.search(rf'href="{path}/stargazers"[^>]*>(.*?)</a>', article, re.S)
        forks = re.search(rf'href="{path}/(?:forks|network/members[^"]*)"[^>]*>(.*?)</a>', article, re.S)
        description = _DESCRIPTION_RE.search(article)
        language = _LANGUAGE_RE.search(article)
        built_by = _BUILT_BY_RE.search(article)
        stars_this_week = _STARS_THIS_WEEK_RE.search(_text(article))
        repos.append(
            {
                "rank": len(repos) + 1,
                "repo": f"{owner}/{name}",
                "url": f"https://github.com/{owner}/{name}",
                "description": (_text(description.group(1)) or None) if description else None,
                "language": (_text(language.group(1)) or None) if language else None,
                "stars": _count(stars.group(1)) if stars else None,
                "forks": _count(forks.group(1)) if forks else None,
                "stars_this_week": _count(stars_this_week.group(1)) if stars_this_week else None,
                "built_by": _AVATAR_RE.findall(built_by.group(1)) if built_by else [],
            }
        )
    return repos


def week_label(moment: dt.datetime) -> str:
    year, week, _ = moment.isocalendar()
    return f"{year}-W{week:02d}"


def _cell(value) -> str:
    if value is None:
        return "–"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_digest(repos: list[dict], collected_at: dt.datetime) -> str:
    year, week, _ = collected_at.isocalendar()
    monday = dt.date.fromisocalendar(year, week, 1)
    sunday = monday + dt.timedelta(days=6)
    lines = [
        f"# GitHub Trending — {week_label(collected_at)}",
        "",
        f"Week of {monday} to {sunday}. "
        f"Collected {collected_at:%Y-%m-%d %H:%M} UTC from <{TRENDING_URL}>.",
        "",
        "| # | Repository | Language | Stars this week | Total stars | Description |",
        "|--:|---|---|--:|--:|---|",
    ]
    for repo in repos:
        lines.append(
            f"| {repo['rank']} | [{repo['repo']}]({repo['url']}) | {_cell(repo['language'])} "
            f"| {_cell(repo['stars_this_week'])} | {_cell(repo['stars'])} "
            f"| {_cell(repo['description'])} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, repos: list[dict], collected_at: dt.datetime) -> list[Path]:
    week = week_label(collected_at)
    data_path = root / "data" / f"{week}.json"
    digest_path = root / "digests" / f"{week}.md"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "week": week,
        "collected_at": collected_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": TRENDING_URL,
        "repositories": repos,
    }
    data_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest_path.write_text(render_digest(repos, collected_at), encoding="utf-8")
    return [data_path, digest_path]


def update_index(root: Path) -> bool:
    """Rewrite the digest list between the index markers in README.md."""
    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8") if readme.exists() else ""
    start, end = content.find(INDEX_START), content.find(INDEX_END)
    if start == -1 or end < start:
        print("warning: README.md has no digest index markers; index not updated", file=sys.stderr)
        return False
    digests = sorted((root / "digests").glob("*.md"), reverse=True)
    entries = "\n".join(f"- [{path.stem}](digests/{path.name})" for path in digests)
    content = content[: start + len(INDEX_START)] + "\n" + entries + "\n" + content[end:]
    readme.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    collected_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    page = fetch(TRENDING_URL)
    repos = parse_trending(page)
    articles = len(re.findall(r"<article\b", page, re.I))
    print(f"page has {articles} <article> elements; parsed {len(repos)} repositories")
    if len(repos) < articles:
        print(
            f"warning: {articles - len(repos)} <article> elements were not parsed; check the trending page markup",
            file=sys.stderr,
        )
    if not repos:
        print(
            "error: no repositories parsed from the trending page; its markup may have changed",
            file=sys.stderr,
        )
        return 1
    if all(repo["stars_this_week"] is None for repo in repos):
        print("warning: no 'stars this week' counts parsed; check the trending page markup", file=sys.stderr)
    for path in write_outputs(ROOT, repos, collected_at):
        print(f"wrote {path.relative_to(ROOT)}")
    update_index(ROOT)
    print(f"collected {len(repos)} repositories for {week_label(collected_at)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
