import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("snapshot", Path(__file__).parents[1] / "scripts/refresh_snapshot.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ArchiveTests(unittest.TestCase):
    def test_current_and_archived_news_survive_and_reports_stay_on_pendar(self):
        old = {"id": "old", "headline_fa": "قدیمی", "published_at": "2020-01-01", "sources": [{"source_name": "منبع"}]}
        news = {"id": "new", "published_at": "2026-10-29"}
        report = {"id": "report", "editorial_report": {"paragraphs": [{"text_fa": "تألیفی"}]}}
        flagged = {"id": "flagged", "has_editorial_report": True}
        data = {"stories.json": [news, report, flagged], "story/old.json": old,
                "story/new.json": news, "story/report.json": report, "story/flagged.json": flagged,
                "press-source-stories.json": {"منبع": [old, news, report, flagged]}}
        MODULE.partition_news(data, {})
        self.assertEqual([x["id"] for x in data["stories.json"]], ["new"])
        self.assertEqual([x["id"] for x in data["news-archive.json"]], ["new", "old"])
        self.assertEqual(set(data["pendar-reports.json"]), {"report", "flagged"})
        self.assertNotIn("story/report.json", data)
        self.assertNotIn("story/flagged.json", data)
        self.assertEqual(data["news-archive.json"][1]["source_names"], ["منبع"])
        self.assertEqual(len(data["press-source-stories.json"]["منبع"]), 2)


if __name__ == "__main__":
    unittest.main()
