# trending-digest

Weekly digest of GitHub's trending repositories.

Every Sunday at 12:00 UTC (20:00 Asia/Taipei), the [Weekly trending digest](.github/workflows/weekly-trending.yml)
workflow fetches <https://github.com/trending?since=weekly> (all languages) and commits:

- `digests/<year>-W<week>.md`: a Markdown table of that week's top 50 trending repositories
- `data/<year>-W<week>.json`: the same data as JSON (rank, repo, description, language, stars, forks, stars this week, built by, source page)

The all-languages page lists only 10-25 repositories, so the collector also reads the weekly
trending page of each language in `LANGUAGES` (`collect.py`). Repositories from the all-languages
page come first in GitHub's order; the rest follow by stars this week, up to 50.

Repositories listed in [`exclude.txt`](exclude.txt) are left out, e.g. meta repositories such as
plugin directories. Add one `owner/name` per line.

Weeks are ISO weeks (Monday to Sunday, UTC). A second run in the same week overwrites that week's files.

## Usage

```sh
python3 collect.py       # fetch the page, write this week's files, update the index below
python3 -m unittest      # parser and output tests (offline, uses tests/fixtures)
```

Standard library only (tested on Python 3.11).

To collect outside the schedule: **Actions → Weekly trending digest → Run workflow**.
If GitHub changes the trending page markup and nothing can be parsed, the run fails instead of committing an empty digest.

## Digests

<!-- digests:start -->
- [2026-W44](digests/2026-W44.md)
- [2026-W43](digests/2026-W43.md)
- [2026-W42](digests/2026-W42.md)
- [2026-W41](digests/2026-W41.md)
- [2026-W40](digests/2026-W40.md)
<!-- digests:end -->
