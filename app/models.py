from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MatchUser(Base):
    __tablename__ = "match_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nickname: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(30), default="")
    age: Mapped[int] = mapped_column(Integer)
    is_age_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    prefers_private_profile: Mapped[bool] = mapped_column(Boolean, default=True)
    public_bio: Mapped[str] = mapped_column(String(500), default="")
    hobbies: Mapped[str] = mapped_column(String(300), default="")
    drink_style: Mapped[str] = mapped_column(String(120), default="casual")
    preferred_stations: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sent_match_requests: Mapped[list["MatchRequestRecord"]] = relationship(
        back_populates="requester", foreign_keys="MatchRequestRecord.requester_id"
    )
    received_match_requests: Mapped[list["MatchRequestRecord"]] = relationship(
        back_populates="target_user", foreign_keys="MatchRequestRecord.target_user_id"
    )
    sent_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="sender", foreign_keys="ChatMessage.sender_id"
    )
    created_social_posts: Mapped[list["SocialPostDraft"]] = relationship(back_populates="creator")
    submitted_reports: Mapped[list["SafetyReport"]] = relationship(
        back_populates="reporter", foreign_keys="SafetyReport.reporter_id"
    )
    blocked_users: Mapped[list["UserBlock"]] = relationship(
        back_populates="blocker", foreign_keys="UserBlock.blocker_id"
    )


class StationVenue(Base):
    __tablename__ = "station_venues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_name: Mapped[str] = mapped_column(String(40), index=True)
    venue_name: Mapped[str] = mapped_column(String(120))
    walk_minutes: Mapped[int] = mapped_column(Integer)
    address_hint: Mapped[str] = mapped_column(String(200), default="")
    open_hours: Mapped[str] = mapped_column(String(120), default="")
    is_safety_checked: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MatchRequestRecord(Base):
    __tablename__ = "match_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("match_users.id"), index=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("match_users.id"), index=True)
    selected_station: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    denied_reason: Mapped[str] = mapped_column(String(200), default="")

    requester: Mapped[MatchUser] = relationship(back_populates="sent_match_requests", foreign_keys=[requester_id])
    target_user: Mapped[MatchUser] = relationship(back_populates="received_match_requests", foreign_keys=[target_user_id])
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="match_request", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    match_request_id: Mapped[int] = mapped_column(ForeignKey("match_requests.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("match_users.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    match_request: Mapped[MatchRequestRecord] = relationship(back_populates="messages")
    sender: Mapped[MatchUser] = relationship(back_populates="sent_messages", foreign_keys=[sender_id])


class SafetyReport(Base):
    __tablename__ = "safety_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("match_users.id"), index=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("match_users.id"), index=True)
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reporter: Mapped[MatchUser] = relationship(back_populates="submitted_reports", foreign_keys=[reporter_id])


class UserBlock(Base):
    __tablename__ = "user_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    blocker_id: Mapped[int] = mapped_column(ForeignKey("match_users.id"), index=True)
    blocked_user_id: Mapped[int] = mapped_column(ForeignKey("match_users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    blocker: Mapped[MatchUser] = relationship(back_populates="blocked_users", foreign_keys=[blocker_id])


class SafetyAuditLog(Base):
    __tablename__ = "safety_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SocialPostDraft(Base):
    __tablename__ = "social_post_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("match_users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(30), index=True)
    content: Mapped[str] = mapped_column(String(280))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    external_post_id: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator: Mapped[MatchUser] = relationship(back_populates="created_social_posts")
