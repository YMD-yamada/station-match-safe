"""既存SQLite/Postgresに password_hash を追加する軽量マイグレーション。"""

from sqlalchemy import inspect, text

from app.db import engine


def ensure_password_hash_column() -> None:
    insp = inspect(engine)
    if not insp.has_table("match_users"):
        return
    cols = {c["name"] for c in insp.get_columns("match_users")}
    if "password_hash" in cols:
        return
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("ALTER TABLE match_users ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT ''"))
        else:
            conn.execute(text("ALTER TABLE match_users ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT ''"))
