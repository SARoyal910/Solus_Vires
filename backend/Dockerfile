FROM python:3.12-slim

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
