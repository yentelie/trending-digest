# trending-digest

Weekly digest of GitHub's trending repositories.

Every Sunday at 22:00 UTC, the [Weekly trending digest](.github/workflows/weekly-trending.yml)
workflow fetches <https://github.com/trending?since=weekly> (all languages) and commits:

- `digests/<year>-W<week>.md`: a Markdown table of that week's trending repositories
- `data/<year>-W<week>.json`: the same data as JSON (rank, repo, description, language, stars, forks, stars this week, built by)

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
_No digests yet._
<!-- digests:end -->
