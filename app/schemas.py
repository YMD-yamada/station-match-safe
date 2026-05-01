from pydantic import BaseModel, Field


class MatchUserCreate(BaseModel):
    nickname: str = Field(min_length=2, max_length=80)
    email: str
    phone: str = ""
    age: int = Field(ge=20, le=99)
    prefers_private_profile: bool = True
    public_bio: str = ""
    hobbies: list[str] = []
    drink_style: str = "casual"
    preferred_stations: list[str] = []


class MatchRequestCreate(BaseModel):
    requester_id: int
    target_user_id: int
    selected_station: str


class MatchDecisionRequest(BaseModel):
    actor_user_id: int
    action: str = Field(pattern="^(accept|decline)$")
    denied_reason: str = ""


class ChatMessageCreate(BaseModel):
    sender_id: int
    message: str = Field(min_length=1, max_length=800)


class SafetyReportCreate(BaseModel):
    reporter_id: int
    target_user_id: int
    category: str
    description: str


class UserBlockCreate(BaseModel):
    blocker_id: int
    blocked_user_id: int
    reason: str = ""


class SocialPostDraftCreate(BaseModel):
    creator_id: int
    platform: str = Field(pattern="^(x|instagram|threads)$")
    station: str
    preferred_date: str
    highlights: list[str] = []
