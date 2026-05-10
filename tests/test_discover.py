from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def _bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_discover_requires_auth():
    client = TestClient(app)
    res = client.get("/discover")
    assert res.status_code == 401


def test_discover_excludes_self_and_returns_others():
    client = TestClient(app)
    suffix = datetime.utcnow().strftime("%f")
    pwd = "test-password-secure-01"
    a = client.post(
        "/users",
        json={
            "nickname": f"alpha_d_{suffix}",
            "email": f"alpha_d_{suffix}@example.com",
            "age": 24,
            "password": pwd,
        },
    )
    assert a.status_code == 200, a.text
    ak = a.json()
    b = client.post(
        "/users",
        json={
            "nickname": f"beta_d_{suffix}",
            "email": f"beta_d_{suffix}@example.com",
            "age": 26,
            "password": pwd,
        },
    )
    assert b.status_code == 200, b.text
    bk = b.json()

    res = client.get("/discover", headers=_bearer(ak["access_token"]))
    assert res.status_code == 200
    ids = {x["id"] for x in res.json().get("items", [])}

    assert ak["user_id"] not in ids
    assert bk["user_id"] in ids
