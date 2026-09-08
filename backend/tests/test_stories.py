from tests.conftest import make_published_story


def test_feed_ranks_by_importance_not_time(client, db):
    # Low importance created LATER; must still rank below high importance.
    make_published_story(db, importance=0.3, headline="کم‌اهمیت")
    make_published_story(db, importance=0.9, headline="پراهمیت")
    r = client.get("/api/v1/stories")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["items"][0]["headline_fa"] == "پراهمیت"
    assert body["items"][0]["importance_score"] >= body["items"][1]["importance_score"]


def test_story_detail_separates_four_layers(client, db):
    story = make_published_story(db, importance=0.7)
    r = client.get(f"/api/v1/stories/{story.id}")
    assert r.status_code == 200
    d = r.json()
    # The four layers are distinct fields, never merged.
    assert d["facts"] == ["این قطعی است."]
    assert d["uncertainties"] == ["این هنوز نامشخص است."]
    assert len(d["source_views"]) == 1
    assert d["source_views"][0]["source_name"].startswith("Reuters")
    # Citations present with link, headline, no full article body.
    assert d["sources"][0]["article_url"]
    assert "raw_content" not in d


def test_story_404(client):
    assert client.get("/api/v1/stories/does-not-exist").status_code == 404


def test_ask_is_grounded_only_in_story(client, db):
    story = make_published_story(db, importance=0.7)
    r = client.post(
        f"/api/v1/stories/{story.id}/ask",
        json={"question": "چرا این خبر مهم است؟"},
    )
    assert r.status_code == 200
    ans = r.json()
    assert ans["inferred"] is False
    assert ans["ai_available"] is False
    assert "این قطعی است." in ans["used_facts"]
    assert ans["note"]  # honest note that AI answering is not yet on


def test_ask_empty_question_rejected(client, db):
    story = make_published_story(db, importance=0.5)
    r = client.post(f"/api/v1/stories/{story.id}/ask", json={"question": "   "})
    assert r.status_code == 422


def test_feed_category_filter(client, db):
    make_published_story(db, importance=0.6)  # economy
    r = client.get("/api/v1/stories?category=technology")
    assert r.json()["total"] == 0
    r2 = client.get("/api/v1/stories?category=economy")
    assert r2.json()["total"] == 1
