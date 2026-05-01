from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def run() -> None:
    client = TestClient(app)
    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    user_a_res = client.post(
        "/users",
        json={
            "nickname": f"user_a_{suffix}",
            "email": f"user_a_{suffix}@example.com",
            "age": 28,
            "hobbies": ["jazz"],
            "preferred_stations": ["熊谷"],
        },
    )
    user_b_res = client.post(
        "/users",
        json={
            "nickname": f"user_b_{suffix}",
            "email": f"user_b_{suffix}@example.com",
            "age": 26,
            "hobbies": ["sports"],
            "preferred_stations": ["上尾"],
        },
    )
    if user_a_res.status_code != 200 or user_b_res.status_code != 200:
        raise RuntimeError(
            f"user create failed: A={user_a_res.status_code} {user_a_res.text} B={user_b_res.status_code} {user_b_res.text}"
        )
    user_a = user_a_res.json()
    user_b = user_b_res.json()
    venues = client.get("/venues", params={"station": "熊谷"}).json()
    match = client.post(
        "/matches",
        json={
            "requester_id": user_a["id"],
            "target_user_id": user_b["id"],
            "selected_station": "熊谷",
        },
    ).json()
    decision = client.post(
        f"/matches/{match['id']}/decision",
        json={"actor_user_id": user_b["id"], "action": "accept"},
    ).json()
    message = client.post(
        f"/matches/{match['id']}/messages",
        json={"sender_id": user_a["id"], "message": "駅近で1時間だけどうですか？"},
    ).json()
    draft = client.post(
        "/social/drafts",
        json={
            "creator_id": user_a["id"],
            "platform": "x",
            "station": "熊谷",
            "preferred_date": "金曜夜",
            "highlights": ["ジャズ", "スポーツ"],
        },
    ).json()
    client.post(f"/social/drafts/{draft['id']}/approve", params={"actor_user_id": user_a["id"]})
    publish = client.post(f"/social/drafts/{draft['id']}/publish", params={"actor_user_id": user_a["id"]}).json()
    print(
        {
            "user_ids": [user_a["id"], user_b["id"]],
            "venues_count": venues.get("count"),
            "match_status": match.get("status"),
            "decision_status": decision.get("status"),
            "message_id": message.get("id"),
            "social_post_status": publish.get("status"),
        }
    )


if __name__ == "__main__":
    run()
