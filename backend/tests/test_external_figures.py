from scripts.collect_external_figures import classify


class FakeResult:
    data = {"posts": [
        {"id": "1", "publish": True, "topic_fa": "سیاست خارجی", "summary_fa": "یک موضع عمومی تازه."},
        {"id": "2", "publish": False, "topic_fa": "", "summary_fa": ""},
    ]}


class FakeProvider:
    name = "test"
    def generate(self, **kwargs):
        return FakeResult()


def test_classify_keeps_provenance(monkeypatch):
    monkeypatch.setattr("scripts.collect_external_figures.get_provider", lambda: FakeProvider())
    rows = [
        {"id": "1", "text_html": "<p>Hello</p>", "url": "https://truthsocial.com/x/1",
         "created_at": "2026-10-03T00:00:00Z", "media": []},
        {"id": "2", "text_html": "<p>Promo</p>", "url": "https://truthsocial.com/x/2",
         "created_at": "2026-10-03T00:01:00Z", "media": []},
    ]
    out = classify(rows)
    assert len(out) == 1
    assert out[0]["handle"] == "donald-trump"
    assert out[0]["platform"] == "truthsocial"
    assert out[0]["source_language"] == "en"
    assert out[0]["url"].endswith("/1")
