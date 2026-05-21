from pydantic import BaseModel


class ContactSubmission(BaseModel):
    safe_name: str = ""
    safe_contact: str = ""
    message: str


class ContactResponse(BaseModel):
    ok: bool
    message: str
