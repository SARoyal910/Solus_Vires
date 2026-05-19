from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

app = FastAPI(title="Solus Vires API")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/contact")
async def contact(
    safe_name: str = Form(default=""),
    safe_contact: str = Form(default=""),
    message: str = Form(default=""),
):
    """
    Basic contact endpoint.

    NOTE:
    - Intentionally does NOT store anything yet.
    - In a real deployment, you'd:
      * Store in an encrypted DB, OR
      * Send to a secure inbox, and
      * Add auto-expiry for safety.
    """
    print("New contact message:")
    print(f"Name (optional alias): {safe_name}")
    print(f"Safe contact info: {safe_contact}")
    print(f"Message: {message}")
    return JSONResponse({"ok": True})
