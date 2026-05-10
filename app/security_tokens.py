"""認証ヘルパ（JWT・パスワードハッシュ）。本番では JWT_SECRET を必ず環境変数で上書きしてください。"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MatchUser

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "dev-jwt-secret-change-me-32bytes-plus!!!",
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", "60"))

security = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_user_id(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="ログインの有効期限が切れました") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="ログイン情報が無効です") from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> MatchUser:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="ログインが必要です")
    uid = decode_user_id(credentials.credentials)
    user = db.query(MatchUser).filter(MatchUser.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="ユーザーが見つかりません")
    return user
