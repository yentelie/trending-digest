import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
