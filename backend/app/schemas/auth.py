from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.\-]+$")
    password: str = Field(min_length=10, max_length=256)


class RegisterResponse(BaseModel):
    ok: bool
    recovery_codes: list[str]


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    ok: bool


class RecoverRequest(BaseModel):
    username: str
    recovery_code: str
    new_password: str = Field(min_length=10, max_length=256)


class RecoverResponse(BaseModel):
    ok: bool


class MeResponse(BaseModel):
    username: str
    evidence_pin_set: bool
