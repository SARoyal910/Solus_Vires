# Solus Vires

Solus Vires is a public safety and resource platform for domestic abuse survivors, families, and advocacy partners.

This repository currently contains a Phase 1 foundation:

- Static public resource pages
- FastAPI backend with health and contact endpoints
- Nginx reverse proxy configuration
- Docker Compose development/deployment skeleton
- Safety-minded copy that avoids false emergency dispatch claims

## Local Development

```bash
cd /Users/saroyal/Projects/solusvires
source .venv/bin/activate
python -m uvicorn backend.app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Useful routes:

```text
GET  /api/health
POST /api/contact
GET  /docs
```

## Docker

Create a local env file from the example before running Docker:

```bash
cp .env.example .env
```

Set a strong `POSTGRES_PASSWORD`, then run:

```bash
docker compose up --build
```

## Safety Boundaries

This app is not yet an emergency dispatch system. Real-time location sharing, emergency response, partner referral workflows, and survivor accounts require additional privacy, legal, mobile, reliability, and advocacy-partner design before launch.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the build roadmap.
