import contextlib
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import collect

FIXTURE = Path(__file__).parent / "fixtures" / "trending_weekly.html"
SUNDAY_EVENING = dt.datetime(2026, 10, 4, 22, 0, tzinfo=dt.timezone.utc)


class ParseTrendingTest(unittest.TestCase):
    def setUp(self):
        self.repos = collect.parse_trending(FIXTURE.read_text(encoding="utf-8"))

    def test_finds_every_article_in_page_order(self):
        self.assertEqual(
            [repo["repo"] for repo in self.repos],
            ["acme/rocket", "solo/quiet-lib", "big-org/agent.kit"],
        )
        self.assertEqual([repo["rank"] for repo in self.repos], [1, 2, 3])

    def test_full_entry(self):
        self.assertEqual(
            self.repos[0],
            {
                "rank": 1,
                "repo": "acme/rocket",
                "url": "https://github.com/acme/rocket",
                "description": "Fast & small build tool | zero config",
                "language": "Python",
                "stars": 38110,
                "forks": 5487,
                "stars_this_week": 2381,
                "built_by": ["alice", "bob"],
                "source_page": None,
            },
        )

    def test_missing_fields_and_legacy_fork_link(self):
        repo = self.repos[1]
        self.assertIsNone(repo["description"])
        self.assertIsNone(repo["language"])
        self.assertEqual(repo["stars"], 7)
        self.assertEqual(repo["forks"], 0)
        self.assertEqual(repo["stars_this_week"], 1)
        self.assertEqual(repo["built_by"], [])

    def test_emoji_description_and_dotted_name(self):
        repo = self.repos[2]
        self.assertEqual(repo["description"], "\U0001F680 Agents that ship")
        self.assertEqual(repo["stars_this_week"], 10518)

    def test_page_without_articles(self):
        self.assertEqual(collect.parse_trending("<html><h2><a href='/a/b'>x</a></h2></html>"), [])


def entry(repo, stars_this_week):
    return {"rank": 0, "repo": repo, "stars_this_week": stars_this_week}


class MergeTest(unittest.TestCase):
    def test_main_page_order_then_language_pages_by_stars(self):
        merged = collect.merge(
            [entry("a/one", 5), entry("a/two", 900)],
            [[entry("b/low", 10), entry("A/One", 1000)], [entry("c/high", 500), entry("c/none", None)]],
            excludes=set(),
            limit=50,
        )
        self.assertEqual([repo["repo"] for repo in merged], ["a/one", "a/two", "c/high", "b/low", "c/none"])
        self.assertEqual([repo["rank"] for repo in merged], [1, 2, 3, 4, 5])

    def test_excludes_case_insensitively_and_caps_at_limit(self):
        merged = collect.merge(
            [entry("Cursor/Plugins", 9), entry("a/one", 8)],
            [[entry(f"x/{n}", n) for n in range(10)]],
            excludes={"cursor/plugins"},
            limit=4,
        )
        self.assertEqual([repo["repo"] for repo in merged], ["a/one", "x/9", "x/8", "x/7"])

    def test_load_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "exclude.txt"
            self.assertEqual(collect.load_excludes(path), set())
            path.write_text("# comment\n\nCursor/Plugins  # meta\nanthropics/claude-plugins-official\n", encoding="utf-8")
            self.assertEqual(collect.load_excludes(path), {"cursor/plugins", "anthropics/claude-plugins-official"})

    def test_repo_exclude_file_parses(self):
        excludes = collect.load_excludes(Path(collect.__file__).parent / collect.EXCLUDE_FILE)
        self.assertIn("anthropics/claude-plugins-official", excludes)
        self.assertIn("cursor/plugins", excludes)


class OutputTest(unittest.TestCase):
    def setUp(self):
        self.repos = collect.parse_trending(FIXTURE.read_text(encoding="utf-8"))

    def test_week_label_uses_iso_week(self):
        self.assertEqual(collect.week_label(SUNDAY_EVENING), "2026-W40")
        self.assertEqual(collect.week_label(dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc)), "2026-W53")

    def test_render_digest(self):
        digest = collect.render_digest(self.repos, SUNDAY_EVENING)
        self.assertTrue(digest.startswith("# GitHub Trending — 2026-W40\n"))
        self.assertIn("Week of 2026-09-28 to 2026-10-04.", digest)
        self.assertIn(
            "| 1 | [acme/rocket](https://github.com/acme/rocket) | Python | 2,381 | 38,110 "
            "| Fast & small build tool \\| zero config |",
            digest,
        )
        self.assertIn("| 2 | [solo/quiet-lib](https://github.com/solo/quiet-lib) | – | 1 | 7 | – |", digest)

    def test_write_outputs_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                f"# Title\n\n{collect.INDEX_START}\n_No digests yet._\n{collect.INDEX_END}\n\nFooter\n",
                encoding="utf-8",
            )
            (root / "digests").mkdir()
            (root / "digests" / "2026-W39.md").write_text("old\n", encoding="utf-8")

            collect.write_outputs(root, self.repos, SUNDAY_EVENING)
            self.assertTrue(collect.update_index(root))

            data = json.loads((root / "data" / "2026-W40.json").read_text(encoding="utf-8"))
            self.assertEqual(data["week"], "2026-W40")
            self.assertEqual(data["collected_at"], "2026-10-04T22:00:00Z")
            self.assertEqual(len(data["repositories"]), 3)
            self.assertTrue((root / "digests" / "2026-W40.md").exists())
            self.assertEqual(
                (root / "README.md").read_text(encoding="utf-8"),
                f"# Title\n\n{collect.INDEX_START}\n"
                "- [2026-W40](digests/2026-W40.md)\n"
                "- [2026-W39](digests/2026-W39.md)\n"
                f"{collect.INDEX_END}\n\nFooter\n",
            )

    def test_update_index_without_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Title\n", encoding="utf-8")
            self.assertFalse(collect.update_index(root))
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), "# Title\n")


class MainTest(unittest.TestCase):
    def run_main(self, page):
        stdout, stderr = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(collect, "ROOT", Path(tmp)), \
                mock.patch.object(collect, "fetch", return_value=page) as fetch, \
                mock.patch.object(collect, "FETCH_DELAY", 0), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = collect.main()
            written = sorted(str(path.relative_to(tmp)) for path in Path(tmp).rglob("*.*"))
            self.fetched = [call.args[0] for call in fetch.call_args_list]
        return code, stdout.getvalue(), stderr.getvalue(), written

    def test_reports_unparsed_articles(self):
        page = FIXTURE.read_text(encoding="utf-8").replace(
            "</main>", '<article class="Box-row"><h2>no repo link</h2></article></main>'
        )
        code, out, err, written = self.run_main(page)
        self.assertEqual(code, 0)
        self.assertIn("trending: page has 4 <article> elements; parsed 3 repositories", out)
        self.assertIn("warning: trending: 1 <article> elements were not parsed", err)
        self.assertEqual(len(written), 2)

    def test_fetches_every_language_page_and_dedupes(self):
        code, out, err, written = self.run_main(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(self.fetched[0], collect.TRENDING_URL)
        self.assertIn("https://github.com/trending/python?since=weekly", self.fetched)
        self.assertEqual(len(self.fetched), 1 + len(collect.LANGUAGES))
        self.assertIn("collected 3 repositories", out)
        self.assertIn("warning: only 3 of 50 repositories", err)

    def test_skips_language_page_that_fails_to_fetch(self):
        page = FIXTURE.read_text(encoding="utf-8")
        responses = [page, OSError("boom")] + [page] * (len(collect.LANGUAGES) - 1)
        stdout, stderr = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(collect, "ROOT", Path(tmp)), \
                mock.patch.object(collect, "fetch", side_effect=responses), \
                mock.patch.object(collect, "FETCH_DELAY", 0), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(collect.main(), 0)
        self.assertIn(f"warning: trending/{collect.LANGUAGES[0]}: fetch failed (boom); skipped", stderr.getvalue())

    def test_fails_without_repositories(self):
        code, _, err, written = self.run_main("<html><body>blocked</body></html>")
        self.assertEqual(code, 1)
        self.assertIn("error: no repositories parsed", err)
        self.assertEqual(written, [])


if __name__ == "__main__":
    unittest.main()
