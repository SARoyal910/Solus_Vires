# Pinned by digest so every build uses the same base image; Dependabot
# (.github/dependabot.yml) proposes a new digest when the image is patched.
# Python stays on 3.12 to match .python-version and the test stack.
FROM python:3.12-slim@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016

WORKDIR /backend

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations
COPY scripts ./scripts

# Only the web server. Database migrations are an explicit deploy step
# (scripts/migrate.sh, docs/RUNBOOK.md), not something every container start
# or restart does behind your back (engineering review M8). If the schema is
# behind the code, the healthcheck in docker-compose.yml marks this container
# unhealthy and `docker compose up --wait` fails.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
