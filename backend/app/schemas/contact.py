from pydantic import BaseModel, Field


class ContactSubmission(BaseModel):
    safe_name: str = Field(default="", max_length=120)
    safe_contact: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=20_000)


class ContactResponse(BaseModel):
    ok: bool
    message: str


class ContactStatusResponse(BaseModel):
    enabled: bool
    response_days: int
