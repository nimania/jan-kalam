def test_api_info(client):
    r = client.get("/api")
    assert r.status_code == 200
    assert r.json()["app"] == "Jan Kalam"


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_reports_db(client):
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
