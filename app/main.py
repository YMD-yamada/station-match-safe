import logging
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.db_migrate import ensure_password_hash_column
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
    ChatSendBody,
    LoginRequest,
    MatchDecisionBody,
    MatchInviteRequest,
    PasswordChangeRequest,
    ProfilePatchRequest,
    RegisterRequest,
    SafetyReportBody,
    SocialPostDraftBody,
    TokenResponse,
    UserBlockBody,
)
from app.security_tokens import create_access_token, get_current_user, hash_password, verify_password

Base.metadata.create_all(bind=engine)
ensure_password_hash_column()
logger = logging.getLogger("station-match")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="駅のみマッチ 安全MVP API", version="1.0.0")
allow_origins = os.getenv("ALLOW_ORIGINS", "http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in allow_origins if x.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Audit-Key", "X-Metrics-Key"],
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
    "version": "1.1-mvp",
    "age_minimum": 20,
    "notice_not_legal_advice": "以下はサービス運営上の説明であり、個別具体的な法令の解釈・助言ではありません。本格運営では利用規約・プライバシーポリシーを整備することを強く推奨します。",
    "sections": [
        {
            "title": "ご利用資格・年齢について",
            "body": (
                "本サービスは20歳以上の方のみを対象とします。画面上の年齢はユーザー自身の申告に基づく下限チェックであり、運営が身分証等で逐一の年齢確認を実施することを保証するものではありません。"
                " 虚偽の申告、未成年のなりすまし、法令に反する目的の利用は禁止します。"
            ),
        },
        {
            "title": "サービス提供の役割・免責（要約）",
            "body": (
                "本サービスは、地域と駅という条件でユーザーのマッチングに関する情報のやりとりを行うための『場』を提供するものであり、ユーザー同士が交わす飲食・会合の内容・結果・決済について立会いまたは保証しません。"
                " ユーザー間または第三者とのトラブルについては、当事者間で解決をお願いします。"
                " （正式版では利用規約に整理した損害責任や利用停止条件などを明記することが望ましいです。）"
            ),
        },
        {
            "title": "運営上のコンテンツ方針",
            "body": (
                "実在しない人物の装い・欺瞞となるプロフィールは禁止です。双方の明示的な同意がない限り第三者への連絡先の横流しや、挑発的な書き込みを助長しないよう運営上のモデレーションまたは通報機能を活用します。"
            ),
        },
        {
            "title": "マッチングとメッセージ",
            "body": (
                "双方が承認するまでアプリ外連絡先の強要や不適切な接触をしないでください。"
                " 承認済みのマッチのスレッド内でのみメッセージが可能です。"
            ),
        },
        {
            "title": "公開情報・個人情報（要約）",
            "body": (
                "他ユーザーへは主としてニックネームや短文プロフィール、趣向などが公開されます。"
                " メールアドレス・電話番号は原則として本人確認およびアカウント復旧など運営上のために取り扱い、ユーザー同士での無断公開はしないでください。"
                " （正式版では、個人情報の利用目的・第三者提供・保存期間・アクセスログ等をプライバシーポリシーに詳述してください。HTTPSの利用、適切なサーバー・アクセス権限、アクセスログの適切保管が望ましいです。）"
            ),
        },
    ],
}


def _verify_metrics_key(x_metrics_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("METRICS_API_KEY", "").strip()
    if not expected:
        return
    if not x_metrics_key or x_metrics_key != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _verify_audit_export_key(x_audit_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("AUDIT_LOG_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=404, detail="not found")
    if not x_audit_key or x_audit_key != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


NG_TERMS = ["未成年", "無理やり", "会ったら断れない"]
REQUEST_LIMIT = int(os.getenv("API_RATE_LIMIT_PER_MIN", "60"))
REQUEST_WINDOW = timedelta(minutes=1)
REQUEST_BUCKET: dict[str, deque[datetime]] = defaultdict(deque)
METRICS: dict[str, int] = {"request_blocked": 0, "error_count": 0}


@app.on_event("startup")
def _log_security_configuration() -> None:
    if os.getenv("JWT_SECRET", "dev-jwt-secret-change-me-32bytes-plus!!!") == (
        "dev-jwt-secret-change-me-32bytes-plus!!!"
    ):
        logger.warning("JWT_SECRET が開発用デフォルトです。本番では必ず強いランダム値を環境変数で設定してください。")
    if not os.getenv("AUDIT_LOG_API_KEY", "").strip():
        logger.info(
            "AUDIT_LOG_API_KEY 未設定: /safety/audit-logs は 404（非公開）です。運用参照時は環境変数キーを設定し、X-Audit-Key を付けてください。"
        )
    if os.getenv("METRICS_API_KEY", "").strip():
        logger.info("METRICS_API_KEY 設定済: /metrics は X-Metrics-Key ヘッダが一致する場合のみ応答します。")


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
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'"
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


def _blocked_user_ids(db: Session, user_id: int) -> set[int]:
    blocked: set[int] = set()
    rows = db.query(UserBlock).filter(
        or_(UserBlock.blocker_id == user_id, UserBlock.blocked_user_id == user_id)
    ).all()
    for row in rows:
        other = row.blocked_user_id if row.blocker_id == user_id else row.blocker_id
        blocked.add(other)
    return blocked


def _matched_other_ids(db: Session, user_id: int) -> set[int]:
    others: set[int] = set()
    rows = (
        db.query(MatchRequestRecord)
        .filter(
            or_(MatchRequestRecord.requester_id == user_id, MatchRequestRecord.target_user_id == user_id),
            MatchRequestRecord.status.in_(["requested", "accepted"]),
        )
        .all()
    )
    for row in rows:
        others.add(row.target_user_id if row.requester_id == user_id else row.requester_id)
    return others


def _public_user_card(user: MatchUser) -> dict:
    return {
        "id": user.id,
        "nickname": user.nickname,
        "age": user.age,
        "public_bio": user.public_bio or "",
        "hobbies": _split_csv(user.hobbies),
        "drink_style": user.drink_style,
        "preferred_stations": _split_csv(user.preferred_stations),
    }


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


@app.post("/users", response_model=TokenResponse)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(MatchUser).filter(MatchUser.email == payload.email.strip().lower()).first():
        raise HTTPException(status_code=409, detail="このメールはすでに登録されています")
    if db.query(MatchUser).filter(MatchUser.nickname == payload.nickname).first():
        raise HTTPException(status_code=409, detail="このニックネームは使われています")
    if payload.age < SAFETY_POLICY["age_minimum"]:
        raise HTTPException(status_code=400, detail="20歳以上のみ登録できます")
    user = MatchUser(
        nickname=payload.nickname.strip(),
        email=payload.email.strip().lower(),
        password_hash=hash_password(payload.password),
        phone="",
        age=payload.age,
        is_age_verified=True,
        prefers_private_profile=True,
        public_bio="",
        hobbies="",
        drink_style="casual",
        preferred_stations="",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _record_audit(db, user.id, "user_created", f"user_id={user.id}")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user_id=user.id, nickname=user.nickname)


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(MatchUser).filter(MatchUser.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="メールまたはパスワードが正しくありません")
    if not user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="このアカウントは旧形式です。サポートへ連絡するか、別メールで再登録してください。",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="メールまたはパスワードが正しくありません")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user_id=user.id, nickname=user.nickname)


def _serialize_me(user: MatchUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "age": user.age,
        "is_age_verified": user.is_age_verified,
        "age_declaration_note": "年齢は届出（自己申告）による下限チェックであり、身分証の提出を求める年齢確認ではありません。",
        "public_bio": user.public_bio,
        "hobbies": _split_csv(user.hobbies),
        "drink_style": user.drink_style,
        "preferred_stations": _split_csv(user.preferred_stations),
        "phone": user.phone,
        "created_at": user.created_at.isoformat(),
    }


@app.get("/users/me")
def read_me(user: MatchUser = Depends(get_current_user)):
    return _serialize_me(user)


@app.patch("/users/me")
def update_me(payload: ProfilePatchRequest, user: MatchUser = Depends(get_current_user), db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    if "nickname" in data and data["nickname"]:
        exists = (
            db.query(MatchUser)
            .filter(MatchUser.nickname == data["nickname"], MatchUser.id != user.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="このニックネームは使われています")
        user.nickname = data["nickname"].strip()
    if "public_bio" in data and data["public_bio"] is not None:
        user.public_bio = data["public_bio"][:500]
    if "hobbies" in data and data["hobbies"] is not None:
        user.hobbies = ",".join(data["hobbies"][:20])
    if "preferred_stations" in data and data["preferred_stations"] is not None:
        user.preferred_stations = ",".join(data["preferred_stations"][:20])
    if "drink_style" in data and data["drink_style"] is not None:
        user.drink_style = data["drink_style"][:120]
    if "phone" in data and data["phone"] is not None:
        user.phone = (data["phone"] or "")[:30]
    db.commit()
    db.refresh(user)
    _record_audit(db, user.id, "profile_updated", "self")
    return _serialize_me(user)


@app.post("/users/me/password")
def change_password(payload: PasswordChangeRequest, user: MatchUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.password_hash or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="現在のパスワードが正しくありません")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    _record_audit(db, user.id, "password_changed", "self")
    return {"status": "ok"}


@app.get("/discover")
def discover_feed(
    user: MatchUser = Depends(get_current_user),
    station: str = Query("", description="絞り込み駅（任意）"),
    limit: int = Query(24, le=80),
    db: Session = Depends(get_db),
):
    me = user.id
    blocked = _blocked_user_ids(db, me)
    matched_others = _matched_other_ids(db, me)
    query = db.query(MatchUser).filter(MatchUser.id != me)
    if station:
        if station not in TAKASAKI_STATIONS:
            raise HTTPException(status_code=400, detail="対象外の駅です")
        query = query.filter(MatchUser.preferred_stations.contains(station))
    candidates = query.order_by(MatchUser.created_at.desc()).limit(limit * 3).all()
    items: list[dict] = []
    for candidate in candidates:
        if candidate.id in blocked or candidate.id in matched_others:
            continue
        items.append(_public_user_card(candidate))
        if len(items) >= limit:
            break
    return {"count": len(items), "items": items}


@app.get("/matches/mine")
def list_my_matches(user: MatchUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = user.id
    rows = (
        db.query(MatchRequestRecord)
        .filter(
            or_(MatchRequestRecord.requester_id == user_id, MatchRequestRecord.target_user_id == user_id),
        )
        .order_by(MatchRequestRecord.requested_at.desc())
        .all()
    )
    payload = []
    for m in rows:
        other_id = m.target_user_id if m.requester_id == user_id else m.requester_id
        other = db.query(MatchUser).filter(MatchUser.id == other_id).first()
        payload.append(
            {
                "match_id": m.id,
                "status": m.status,
                "role": "requester" if m.requester_id == user_id else "target",
                "selected_station": m.selected_station,
                "requested_at": m.requested_at.isoformat(),
                "accepted_at": m.accepted_at.isoformat() if m.accepted_at else None,
                "other": _public_user_card(other) if other else None,
            }
        )
    return {"items": payload}


@app.get("/users/{user_id}")
def get_user(
    user_id: int,
    _: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
def create_match_request(
    payload: MatchInviteRequest,
    user: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requester_id = user.id
    target_user_id = payload.target_user_id
    if payload.selected_station not in TAKASAKI_STATIONS:
        raise HTTPException(status_code=400, detail="対象外の駅です")
    if requester_id == target_user_id:
        raise HTTPException(status_code=400, detail="自分自身には申請できません")
    requester = db.query(MatchUser).filter(MatchUser.id == requester_id).first()
    target = db.query(MatchUser).filter(MatchUser.id == target_user_id).first()
    if not requester or not target:
        raise HTTPException(status_code=404, detail="user not found")
    pending = (
        db.query(MatchRequestRecord)
        .filter(
            or_(
                (MatchRequestRecord.requester_id == requester_id)
                & (MatchRequestRecord.target_user_id == target_user_id),
                (MatchRequestRecord.requester_id == target_user_id)
                & (MatchRequestRecord.target_user_id == requester_id),
            ),
            MatchRequestRecord.status.in_(["requested", "accepted"]),
        )
        .first()
    )
    if pending:
        raise HTTPException(
            status_code=409,
            detail={"message": "すでに申請済み、またはマッチ済みです", "match_id": pending.id, "status": pending.status},
        )
    if db.query(UserBlock).filter(
        UserBlock.blocker_id == target_user_id, UserBlock.blocked_user_id == requester_id
    ).first():
        raise HTTPException(status_code=403, detail="target user blocked requester")
    match = MatchRequestRecord(
        requester_id=requester_id,
        target_user_id=target_user_id,
        selected_station=payload.selected_station,
        status="requested",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    _record_audit(db, requester_id, "match_requested", f"match_id={match.id}")
    return {"id": match.id, "status": match.status}


@app.post("/matches/{match_id}/decision")
def decide_match(
    match_id: int,
    payload: MatchDecisionBody,
    user: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    match = db.query(MatchRequestRecord).filter(MatchRequestRecord.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    if match.target_user_id != user.id:
        raise HTTPException(status_code=403, detail="only target user can decide")
    if payload.action == "accept":
        match.status = "accepted"
        match.accepted_at = datetime.utcnow()
        _record_audit(db, user.id, "match_accepted", f"match_id={match.id}")
    else:
        match.status = "declined"
        match.denied_reason = payload.denied_reason[:200]
        _record_audit(db, user.id, "match_declined", f"match_id={match.id}")
    db.commit()
    db.refresh(match)
    return {"id": match.id, "status": match.status, "denied_reason": match.denied_reason}


@app.post("/matches/{match_id}/messages")
def send_message(
    match_id: int,
    payload: ChatSendBody,
    user: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    match = db.query(MatchRequestRecord).filter(MatchRequestRecord.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    if match.status != "accepted":
        raise HTTPException(status_code=403, detail="双方承認済みマッチのみ送信可")
    if user.id not in {match.requester_id, match.target_user_id}:
        raise HTTPException(status_code=403, detail="invalid sender")
    lowered = payload.message.lower()
    if any(term in lowered for term in NG_TERMS):
        _record_audit(db, user.id, "message_blocked", f"match_id={match.id}")
        raise HTTPException(status_code=400, detail="安全上の理由で送信できない内容です")
    msg = ChatMessage(match_request_id=match.id, sender_id=user.id, message=payload.message)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "created_at": msg.created_at.isoformat()}


@app.get("/matches/{match_id}/messages")
def list_messages(match_id: int, user: MatchUser = Depends(get_current_user), db: Session = Depends(get_db)):
    match = db.query(MatchRequestRecord).filter(MatchRequestRecord.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    if user.id not in {match.requester_id, match.target_user_id}:
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
def create_report(
    payload: SafetyReportBody,
    user: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = SafetyReport(
        reporter_id=user.id,
        target_user_id=payload.target_user_id,
        category=payload.category[:40],
        description=payload.description[:2000],
        status="open",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    _record_audit(db, user.id, "report_created", f"report_id={report.id}")
    return {"id": report.id, "status": report.status}


@app.post("/safety/blocks")
def block_user(
    payload: UserBlockBody,
    user: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    blocker_id = user.id
    blocked_user_id = payload.blocked_user_id
    exists = db.query(UserBlock).filter(
        UserBlock.blocker_id == blocker_id, UserBlock.blocked_user_id == blocked_user_id
    ).first()
    if exists:
        return {"id": exists.id, "status": "already_blocked"}
    block = UserBlock(
        blocker_id=blocker_id,
        blocked_user_id=blocked_user_id,
        reason=payload.reason[:200],
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    _record_audit(db, blocker_id, "user_blocked", f"blocked_user_id={blocked_user_id}")
    return {"id": block.id, "status": "blocked"}


@app.get("/safety/audit-logs")
def get_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_audit_export_key),
):
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
def create_social_draft(
    payload: SocialPostDraftBody,
    user: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.station not in TAKASAKI_STATIONS:
        raise HTTPException(status_code=400, detail="対象外の駅です")
    topics = " ".join(payload.highlights[:3]) if payload.highlights else "駅近で気軽に"
    content = f"{payload.station}駅周辺で20歳以上の飲み友募集。{payload.preferred_date}候補。{topics} #駅近 #飲み友"
    draft = SocialPostDraft(creator_id=user.id, platform=payload.platform, content=content[:280], status="draft")
    db.add(draft)
    db.commit()
    db.refresh(draft)
    _record_audit(db, user.id, "social_draft_created", f"draft_id={draft.id}")
    return {"id": draft.id, "platform": draft.platform, "status": draft.status, "content": draft.content}


@app.post("/social/drafts/{draft_id}/approve")
def approve_social_draft(
    draft_id: int,
    user: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draft = db.query(SocialPostDraft).filter(SocialPostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="draft not found")
    if draft.creator_id != user.id:
        raise HTTPException(status_code=403, detail="only creator can approve")
    draft.status = "approved"
    draft.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)
    _record_audit(db, user.id, "social_draft_approved", f"draft_id={draft.id}")
    return {"id": draft.id, "status": draft.status, "approved_at": draft.approved_at.isoformat()}


@app.post("/social/drafts/{draft_id}/publish")
def publish_social_draft(
    draft_id: int,
    user: MatchUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draft = db.query(SocialPostDraft).filter(SocialPostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="draft not found")
    if draft.creator_id != user.id:
        raise HTTPException(status_code=403, detail="only creator can publish")
    if draft.status != "approved":
        raise HTTPException(status_code=400, detail="approved draft required before publish")
    draft.status = "published"
    draft.published_at = datetime.utcnow()
    draft.external_post_id = f"{draft.platform}-{draft.id}-{int(draft.published_at.timestamp())}"
    db.commit()
    db.refresh(draft)
    _record_audit(db, user.id, "social_draft_published", f"draft_id={draft.id}")
    return {"id": draft.id, "status": draft.status, "external_post_id": draft.external_post_id}


@app.get("/metrics")
def metrics(_: None = Depends(_verify_metrics_key)):
    return METRICS


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
