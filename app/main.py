import logging
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.models import (
    ChatMessage,
    MatchRequestRecord,
    MatchUser,
    SafetyAuditLog,
    SafetyReport,
    SocialPostDraft,
    StationVenue,
    UserBlock,
)
from app.schemas import (
    ChatMessageCreate,
    MatchDecisionRequest,
    MatchRequestCreate,
    MatchUserCreate,
    SafetyReportCreate,
    SocialPostDraftCreate,
    UserBlockCreate,
)

Base.metadata.create_all(bind=engine)
logger = logging.getLogger("station-match")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="駅のみマッチ 安全MVP API", version="1.0.0")
allow_origins = os.getenv("ALLOW_ORIGINS", "http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in allow_origins if x.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

TAKASAKI_STATIONS = [
    "上尾",
    "北上尾",
    "桶川",
    "北本",
    "鴻巣",
    "北鴻巣",
    "吹上",
    "行田",
    "熊谷",
    "籠原",
    "深谷",
    "岡部",
    "本庄",
]
DEFAULT_VENUES = [
    {"station_name": "上尾", "venue_name": "上尾駅前ダイニング", "walk_minutes": 4, "open_hours": "17:00-24:00"},
    {"station_name": "桶川", "venue_name": "桶川駅東口バル", "walk_minutes": 6, "open_hours": "18:00-23:30"},
    {"station_name": "鴻巣", "venue_name": "鴻巣カジュアル酒場", "walk_minutes": 7, "open_hours": "17:30-23:00"},
    {"station_name": "熊谷", "venue_name": "熊谷駅前食堂", "walk_minutes": 5, "open_hours": "17:00-25:00"},
    {"station_name": "深谷", "venue_name": "深谷テラスバル", "walk_minutes": 3, "open_hours": "18:00-24:00"},
    {"station_name": "本庄", "venue_name": "本庄グリル", "walk_minutes": 8, "open_hours": "17:00-23:30"},
]
SAFETY_POLICY = {
    "age_minimum": 20,
    "transparency": "実在ユーザーのみ利用可。架空プロフィールは禁止。",
    "consent_rule": "双方同意前は連絡不可。承認済みマッチのみメッセージ可。",
    "privacy_rule": "公開情報はニックネーム中心。電話番号や詳細住所は非公開。",
}
NG_TERMS = ["未成年", "無理やり", "会ったら断れない"]
REQUEST_LIMIT = int(os.getenv("API_RATE_LIMIT_PER_MIN", "60"))
REQUEST_WINDOW = timedelta(minutes=1)
REQUEST_BUCKET: dict[str, deque[datetime]] = defaultdict(deque)
METRICS: dict[str, int] = {"request_blocked": 0, "error_count": 0}


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    now = datetime.utcnow()
    bucket = REQUEST_BUCKET[ip]
    while bucket and now - bucket[0] > REQUEST_WINDOW:
        bucket.popleft()
    if len(bucket) >= REQUEST_LIMIT:
        METRICS["request_blocked"] += 1
        return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
    bucket.append(now)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception):
    METRICS["error_count"] += 1
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


def _split_csv(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _record_audit(db: Session, actor_id: int | None, event_type: str, detail: str) -> None:
    db.add(SafetyAuditLog(actor_id=actor_id, event_type=event_type, detail=detail[:500]))
    db.commit()


def _seed_venues_if_empty(db: Session) -> None:
    if db.query(StationVenue).count() > 0:
        return
    for item in DEFAULT_VENUES:
        db.add(
            StationVenue(
                station_name=item["station_name"],
                venue_name=item["venue_name"],
                walk_minutes=item["walk_minutes"],
                open_hours=item["open_hours"],
                address_hint="駅徒歩10分以内",
                is_safety_checked=True,
            )
        )
    db.commit()


@app.get("/health")
def health():
    return {"ok": True, "service": "station-match", "version": app.version}


@app.get("/policy/safety")
def get_policy():
    return SAFETY_POLICY


@app.post("/users")
def create_user(payload: MatchUserCreate, db: Session = Depends(get_db)):
    if db.query(MatchUser).filter(MatchUser.email == payload.email).first():
        raise HTTPException(status_code=409, detail="email already exists")
    if payload.age < SAFETY_POLICY["age_minimum"]:
        raise HTTPException(status_code=400, detail="20歳以上のみ登録できます")
    user = MatchUser(
        nickname=payload.nickname,
        email=payload.email,
        phone=payload.phone,
        age=payload.age,
        is_age_verified=True,
        prefers_private_profile=payload.prefers_private_profile,
        public_bio=payload.public_bio[:500],
        hobbies=",".join(payload.hobbies[:20]),
        drink_style=payload.drink_style[:120],
        preferred_stations=",".join(payload.preferred_stations[:20]),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _record_audit(db, user.id, "user_created", f"user_id={user.id}")
    return {"id": user.id, "is_age_verified": user.is_age_verified}


@app.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(MatchUser).filter(MatchUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return {
        "id": user.id,
        "nickname": user.nickname,
        "age": user.age,
        "is_age_verified": user.is_age_verified,
        "public_bio": user.public_bio,
        "hobbies": _split_csv(user.hobbies),
        "drink_style": user.drink_style,
        "preferred_stations": _split_csv(user.preferred_stations),
        "created_at": user.created_at.isoformat(),
    }


@app.get("/stations")
def list_stations():
    return {"items": TAKASAKI_STATIONS}


@app.get("/venues")
def list_venues(station: str = Query("", description="高崎線の駅名"), db: Session = Depends(get_db)):
    _seed_venues_if_empty(db)
    query = db.query(StationVenue).filter(StationVenue.walk_minutes <= 10)
    if station:
        if station not in TAKASAKI_STATIONS:
            raise HTTPException(status_code=400, detail="対象外の駅です")
        query = query.filter(StationVenue.station_name == station)
    rows = query.order_by(StationVenue.station_name.asc()).all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": row.id,
                "station_name": row.station_name,
                "venue_name": row.venue_name,
                "walk_minutes": row.walk_minutes,
                "open_hours": row.open_hours,
                "is_safety_checked": row.is_safety_checked,
            }
            for row in rows
        ],
    }


@app.post("/matches")
def create_match_request(payload: MatchRequestCreate, db: Session = Depends(get_db)):
    if payload.selected_station not in TAKASAKI_STATIONS:
        raise HTTPException(status_code=400, detail="対象外の駅です")
    if payload.requester_id == payload.target_user_id:
        raise HTTPException(status_code=400, detail="自分自身には申請できません")
    requester = db.query(MatchUser).filter(MatchUser.id == payload.requester_id).first()
    target = db.query(MatchUser).filter(MatchUser.id == payload.target_user_id).first()
    if not requester or not target:
        raise HTTPException(status_code=404, detail="user not found")
    if db.query(UserBlock).filter(
        UserBlock.blocker_id == payload.target_user_id, UserBlock.blocked_user_id == payload.requester_id
    ).first():
        raise HTTPException(status_code=403, detail="target user blocked requester")
    match = MatchRequestRecord(
        requester_id=payload.requester_id,
        target_user_id=payload.target_user_id,
        selected_station=payload.selected_station,
        status="requested",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    _record_audit(db, payload.requester_id, "match_requested", f"match_id={match.id}")
    return {"id": match.id, "status": match.status}


@app.post("/matches/{match_id}/decision")
def decide_match(match_id: int, payload: MatchDecisionRequest, db: Session = Depends(get_db)):
    match = db.query(MatchRequestRecord).filter(MatchRequestRecord.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    if match.target_user_id != payload.actor_user_id:
        raise HTTPException(status_code=403, detail="only target user can decide")
    if payload.action == "accept":
        match.status = "accepted"
        match.accepted_at = datetime.utcnow()
        _record_audit(db, payload.actor_user_id, "match_accepted", f"match_id={match.id}")
    else:
        match.status = "declined"
        match.denied_reason = payload.denied_reason[:200]
        _record_audit(db, payload.actor_user_id, "match_declined", f"match_id={match.id}")
    db.commit()
    db.refresh(match)
    return {"id": match.id, "status": match.status, "denied_reason": match.denied_reason}


@app.post("/matches/{match_id}/messages")
def send_message(match_id: int, payload: ChatMessageCreate, db: Session = Depends(get_db)):
    match = db.query(MatchRequestRecord).filter(MatchRequestRecord.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    if match.status != "accepted":
        raise HTTPException(status_code=403, detail="双方承認済みマッチのみ送信可")
    if payload.sender_id not in {match.requester_id, match.target_user_id}:
        raise HTTPException(status_code=403, detail="invalid sender")
    lowered = payload.message.lower()
    if any(term in lowered for term in NG_TERMS):
        _record_audit(db, payload.sender_id, "message_blocked", f"match_id={match.id}")
        raise HTTPException(status_code=400, detail="安全上の理由で送信できない内容です")
    msg = ChatMessage(match_request_id=match.id, sender_id=payload.sender_id, message=payload.message)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "created_at": msg.created_at.isoformat()}


@app.get("/matches/{match_id}/messages")
def list_messages(match_id: int, actor_user_id: int, db: Session = Depends(get_db)):
    match = db.query(MatchRequestRecord).filter(MatchRequestRecord.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    if actor_user_id not in {match.requester_id, match.target_user_id}:
        raise HTTPException(status_code=403, detail="forbidden")
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.match_request_id == match.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return {
        "count": len(rows),
        "items": [
            {"id": r.id, "sender_id": r.sender_id, "message": r.message, "created_at": r.created_at.isoformat()}
            for r in rows
        ],
    }


@app.post("/safety/reports")
def create_report(payload: SafetyReportCreate, db: Session = Depends(get_db)):
    report = SafetyReport(
        reporter_id=payload.reporter_id,
        target_user_id=payload.target_user_id,
        category=payload.category[:40],
        description=payload.description[:2000],
        status="open",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    _record_audit(db, payload.reporter_id, "report_created", f"report_id={report.id}")
    return {"id": report.id, "status": report.status}


@app.post("/safety/blocks")
def block_user(payload: UserBlockCreate, db: Session = Depends(get_db)):
    exists = db.query(UserBlock).filter(
        UserBlock.blocker_id == payload.blocker_id, UserBlock.blocked_user_id == payload.blocked_user_id
    ).first()
    if exists:
        return {"id": exists.id, "status": "already_blocked"}
    block = UserBlock(
        blocker_id=payload.blocker_id,
        blocked_user_id=payload.blocked_user_id,
        reason=payload.reason[:200],
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    _record_audit(db, payload.blocker_id, "user_blocked", f"blocked_user_id={payload.blocked_user_id}")
    return {"id": block.id, "status": "blocked"}


@app.get("/safety/audit-logs")
def get_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(SafetyAuditLog).order_by(SafetyAuditLog.created_at.desc()).limit(min(limit, 200)).all()
    return {
        "items": [
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "event_type": row.event_type,
                "detail": row.detail,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@app.post("/social/drafts")
def create_social_draft(payload: SocialPostDraftCreate, db: Session = Depends(get_db)):
    if payload.station not in TAKASAKI_STATIONS:
        raise HTTPException(status_code=400, detail="対象外の駅です")
    creator = db.query(MatchUser).filter(MatchUser.id == payload.creator_id).first()
    if not creator:
        raise HTTPException(status_code=404, detail="creator not found")
    topics = " ".join(payload.highlights[:3]) if payload.highlights else "駅近で気軽に"
    content = f"{payload.station}駅周辺で20歳以上の飲み友募集。{payload.preferred_date}候補。{topics} #駅近 #飲み友"
    draft = SocialPostDraft(creator_id=payload.creator_id, platform=payload.platform, content=content[:280], status="draft")
    db.add(draft)
    db.commit()
    db.refresh(draft)
    _record_audit(db, payload.creator_id, "social_draft_created", f"draft_id={draft.id}")
    return {"id": draft.id, "platform": draft.platform, "status": draft.status, "content": draft.content}


@app.post("/social/drafts/{draft_id}/approve")
def approve_social_draft(draft_id: int, actor_user_id: int, db: Session = Depends(get_db)):
    draft = db.query(SocialPostDraft).filter(SocialPostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="draft not found")
    if draft.creator_id != actor_user_id:
        raise HTTPException(status_code=403, detail="only creator can approve")
    draft.status = "approved"
    draft.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)
    _record_audit(db, actor_user_id, "social_draft_approved", f"draft_id={draft.id}")
    return {"id": draft.id, "status": draft.status, "approved_at": draft.approved_at.isoformat()}


@app.post("/social/drafts/{draft_id}/publish")
def publish_social_draft(draft_id: int, actor_user_id: int, db: Session = Depends(get_db)):
    draft = db.query(SocialPostDraft).filter(SocialPostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="draft not found")
    if draft.creator_id != actor_user_id:
        raise HTTPException(status_code=403, detail="only creator can publish")
    if draft.status != "approved":
        raise HTTPException(status_code=400, detail="approved draft required before publish")
    draft.status = "published"
    draft.published_at = datetime.utcnow()
    draft.external_post_id = f"{draft.platform}-{draft.id}-{int(draft.published_at.timestamp())}"
    db.commit()
    db.refresh(draft)
    _record_audit(db, actor_user_id, "social_draft_published", f"draft_id={draft.id}")
    return {"id": draft.id, "status": draft.status, "external_post_id": draft.external_post_id}


@app.get("/metrics")
def metrics():
    return METRICS


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
