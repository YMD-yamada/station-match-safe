from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def test_discover_excludes_self_and_returns_cards():
    client = TestClient(app)
    suffix = datetime.utcnow().strftime("%f")
    a = client.post(
        "/users",
        json={
            "nickname": f"alpha_discover_{suffix}",
            "email": f"alpha_discover_{suffix}@example.com",
            "age": 24,
            "hobbies": ["run"],
            "preferred_stations": ["熊谷"],
        },
    ).json()
    b = client.post(
        "/users",
        json={
            "nickname": f"beta_discover_{suffix}",
            "email": f"beta_discover_{suffix}@example.com",
            "age": 26,
            "hobbies": ["music"],
            "preferred_stations": ["熊谷"],
        },
    ).json()
    res = client.get("/discover/users", params={"me": a["id"], "station": "熊谷"})
    assert res.status_code == 200
    data = res.json()
    ids = {x["id"] for x in data["items"]}
    assert a["id"] not in ids
    assert b["id"] in ids
