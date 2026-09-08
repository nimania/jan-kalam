from tests.conftest import make_topic


def test_list_and_get_topic(client, db):
    t = make_topic(db, slug="ai", name_fa="هوش مصنوعی")
    r = client.get("/api/v1/topics")
    assert any(x["slug"] == "ai" for x in r.json())
    r2 = client.get(f"/api/v1/topics/{t.id}")
    assert r2.status_code == 200
    assert r2.json()["name_fa"] == "هوش مصنوعی"


def test_follow_and_unfollow(client, db):
    t = make_topic(db, slug="bitcoin", name_fa="بیت‌کوین")
    headers = {"X-User-Id": "device-123"}
    r = client.post(f"/api/v1/topics/{t.id}/follow", headers=headers)
    assert r.status_code == 200
    assert r.json()["following"] is True
    # Idempotent follow
    r_again = client.post(f"/api/v1/topics/{t.id}/follow", headers=headers)
    assert r_again.json()["following"] is True

    r_del = client.delete(f"/api/v1/topics/{t.id}/follow", headers=headers)
    assert r_del.status_code == 200
    assert r_del.json()["following"] is False


def test_follow_missing_topic_404(client):
    assert client.post("/api/v1/topics/nope/follow").status_code == 404
