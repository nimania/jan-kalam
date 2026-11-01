import unittest
from scripts.import_verified_simorgh import approved, merge, to_news

BASE = {
    "id": "abcdef0123456789abcd",
    "source_url": "https://t.me/simorghdata369/22",
    "review_status": "approved",
    "reviewed_by": "تحریریه پندار",
    "approved_at": "2026-11-02T12:30:00+03:30",
    "source_published_at": "2026-11-01T13:00:00+03:30",
    "approved_headline_fa": "یک خبر مهم و مستقل درباره تازه‌ترین تحولات ایران",
    "approved_summary_fa": "این خبر پس از بررسی جداگانه منابع و انطباق با سند اولیه تهیه شده و تفاوت میان ادعا و تأیید مستقل را روشن می‌کند.",
    "why_it_matters_fa": "این خبر به بررسی پیامدهای سیاسی برای ایران و منطقه کمک می‌کند.",
    "independent_sources": [{"source_name": "منبع مستقل", "article_url": "https://example.com/news"}],
}


class SignalPublicationTests(unittest.TestCase):
    def test_unapproved_not_published(self):
        row = dict(BASE, review_status="pending")
        self.assertEqual(merge([], {"leads": [row]})[0], [])

    def test_approved_has_stable_uuid_and_independent_sources(self):
        self.assertTrue(approved(BASE))
        a = to_news(BASE)
        b = to_news(BASE)
        self.assertEqual(a["id"], b["id"])
        self.assertFalse(a["editorial_report"])
        self.assertEqual(a["source_count"], 1)
        self.assertEqual(a["discovery_source_url"], BASE["source_url"])

    def test_telegram_is_not_independent_corroboration(self):
        row = dict(BASE, independent_sources=[{"source_name": "تلگرام", "article_url": "https://t.me/someother/1"}])
        self.assertFalse(approved(row))

    def test_existing_manual_news_survives(self):
        original = [{"id": "old", "headline_fa": "خبر قبلی", "published_at": "2026-10-01"}]
        results, n = merge(original, {"leads": [BASE]})
        self.assertEqual(n, 1)
        self.assertEqual(len(results), 2)
        again, n = merge(results, {"leads": [BASE]})
        self.assertEqual(n, 0)
        self.assertEqual(len(again), 2)


if __name__ == "__main__":
    unittest.main()
