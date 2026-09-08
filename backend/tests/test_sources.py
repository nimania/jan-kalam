def test_admin_create_and_list_sources(client):
    payload = {
        "name": "Financial Times",
        "feed_url": "https://ft.test/rss",
        "region": "global",
        "reliability_score": 0.85,
        "allow_full_content": False,
    }
    r = client.post("/api/v1/admin/sources", json=payload)
    assert r.status_code == 201
    created = r.json()
    assert created["name"] == "Financial Times"
    assert created["allow_full_content"] is False

    r2 = client.get("/api/v1/sources")
    assert r2.status_code == 200
    names = [s["name"] for s in r2.json()]
    assert "Financial Times" in names


def test_duplicate_source_rejected(client):
    p = {"name": "Politico", "feed_url": "https://p.test/rss"}
    assert client.post("/api/v1/admin/sources", json=p).status_code == 201
    assert client.post("/api/v1/admin/sources", json=p).status_code == 409


def test_disable_source(client):
    r = client.post(
        "/api/v1/admin/sources", json={"name": "Ars Technica", "feed_url": "https://a.test/rss"}
    )
    sid = r.json()["id"]
    upd = client.patch(f"/api/v1/admin/sources/{sid}", json={"enabled": False})
    assert upd.status_code == 200
    assert upd.json()["enabled"] is False
    # enabled_only filter should now hide it
    enabled = client.get("/api/v1/sources?enabled_only=true").json()
    assert all(s["id"] != sid for s in enabled)
