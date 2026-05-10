import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.main import app


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def run() -> None:
    client = TestClient(app)
    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    pwd = "SmokeTest-Password-90210"
    user_a_res = client.post(
        "/users",
        json={
            "nickname": f"user_a_{suffix}",
            "email": f"user_a_{suffix}@example.com",
            "age": 28,
            "password": pwd,
        },
    )
    user_b_res = client.post(
        "/users",
        json={
            "nickname": f"user_b_{suffix}",
            "email": f"user_b_{suffix}@example.com",
            "age": 26,
            "password": pwd,
        },
    )
    if user_a_res.status_code != 200 or user_b_res.status_code != 200:
        raise RuntimeError(
            "user create failed: "
            f"A={user_a_res.status_code} {user_a_res.text} "
            f"B={user_b_res.status_code} {user_b_res.text}"
        )
    user_a = user_a_res.json()
    user_b = user_b_res.json()

    client.patch(
        "/users/me",
        headers=_bearer(user_a["access_token"]),
        json={"preferred_stations": ["熊谷"], "hobbies": ["ジャズ"]},
    )
    client.patch(
        "/users/me",
        headers=_bearer(user_b["access_token"]),
        json={"preferred_stations": ["上尾"], "hobbies": ["スポーツ"]},
    )

    venues = client.get("/venues", params={"station": "熊谷"}).json()

    match_res = client.post(
        "/matches",
        headers=_bearer(user_a["access_token"]),
        json={
            "target_user_id": user_b["user_id"],
            "selected_station": "熊谷",
        },
    )
    if match_res.status_code != 200:
        raise RuntimeError(f"match failed: {match_res.status_code} {match_res.text}")
    match = match_res.json()

    decision = client.post(
        f"/matches/{match['id']}/decision",
        headers=_bearer(user_b["access_token"]),
        json={"action": "accept"},
    ).json()

    message = client.post(
        f"/matches/{match['id']}/messages",
        headers=_bearer(user_a["access_token"]),
        json={"message": "駅近で短時間はいかがですか？"},
    ).json()

    draft = client.post(
        "/social/drafts",
        headers=_bearer(user_a["access_token"]),
        json={
            "platform": "x",
            "station": "熊谷",
            "preferred_date": "金曜夜",
            "highlights": ["ジャズ", "スポーツ"],
        },
    ).json()
    client.post(
        f"/social/drafts/{draft['id']}/approve",
        headers=_bearer(user_a["access_token"]),
    )
    publish = client.post(
        f"/social/drafts/{draft['id']}/publish",
        headers=_bearer(user_a["access_token"]),
    ).json()
    print(
        {
            "user_ids": [user_a["user_id"], user_b["user_id"]],
            "venues_count": venues.get("count"),
            "match_status": match.get("status"),
            "decision_status": decision.get("status"),
            "message_id": message.get("id"),
            "social_post_status": publish.get("status"),
        },
    )


if __name__ == "__main__":
    run()
