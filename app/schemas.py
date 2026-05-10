from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=80)
    email: EmailStr
    age: int = Field(ge=20, le=99)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    nickname: str


class ProfilePatchRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=2, max_length=80)
    public_bio: str | None = Field(default=None, max_length=500)
    hobbies: list[str] | None = None
    preferred_stations: list[str] | None = None
    drink_style: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class MatchInviteRequest(BaseModel):
    target_user_id: int
    selected_station: str


class MatchDecisionBody(BaseModel):
    action: str = Field(pattern="^(accept|decline)$")
    denied_reason: str = ""


class ChatSendBody(BaseModel):
    message: str = Field(min_length=1, max_length=800)


class SafetyReportBody(BaseModel):
    target_user_id: int
    category: str
    description: str


class UserBlockBody(BaseModel):
    blocked_user_id: int
    reason: str = ""


class SocialPostDraftBody(BaseModel):
    platform: str = Field(pattern="^(x|instagram|threads)$")
    station: str
    preferred_date: str
    highlights: list[str] = []
