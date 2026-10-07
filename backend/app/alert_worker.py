"""The check-in alert loop as its own process (SCALE.md Stage 1 item 5).

    python -m app.alert_worker

Runs the same pass as the loop inside the api's lifespan, from the same image,
against the same database. Giving it its own container means a web deploy, a
slow login or an api crash never pauses alerts, and an alert pass never slows
a login. The Postgres advisory lock in CheckinService.run_due_alerts_once
makes it safe to run next to an api that still has CHECKIN_ALERT_LOOP_ENABLED
on during the transition; afterwards turn that flag off on the api.

Liveness: the worker touches ALERT_WORKER_HEARTBEAT_FILE at start and after
every pass, whether the pass ran or was skipped because another process held
the lock. The container healthcheck in docker-compose.yml fails when that
file is older than three check intervals, so a wedged worker shows up in
`docker compose ps` and fails `deploy.sh`'s wait. The Healthchecks.io ping
(HEALTHCHECK_PING_URL) is separate and stricter: only a pass that ran to the
end pings, which is what pages someone.
"""

import asyncio
import logging
import os
import signal
from pathlib import Path

from .core.config import get_settings, production_config_problems
from .services.checkin import CheckinService

logger = logging.getLogger("solusvires.alert_worker")

DEFAULT_HEARTBEAT_FILE = "/tmp/alert-worker-heartbeat"


def heartbeat_file() -> Path:
    return Path(os.getenv("ALERT_WORKER_HEARTBEAT_FILE", DEFAULT_HEARTBEAT_FILE))


def _touch(path: Path) -> None:
    try:
        path.touch()
    except OSError as exc:
        # Only the container healthcheck reads this file; alerts must not care.
        logger.warning("alert_worker_heartbeat_write_failed", extra={"error": type(exc).__name__})


async def run_loop(service: CheckinService, heartbeat: Path, *, stop: asyncio.Event | None = None) -> None:
    """Runs passes every CHECKIN_ALERT_CHECK_SECONDS until `stop` is set.

    A failed pass (database briefly unreachable, say) is logged and the loop
    carries on: alerts silently stopping until a restart is the failure this
    whole process exists to prevent.
    """
    settings = get_settings()
    stop = stop or asyncio.Event()
    _touch(heartbeat)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.checkin_alert_check_seconds)
            break
        except asyncio.TimeoutError:
            pass
        try:
            await asyncio.to_thread(service.run_due_alerts_once)
        except Exception:
            logger.exception("alert_worker_pass_failed")
        _touch(heartbeat)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    problems = production_config_problems(settings)
    if problems:
        # Same refusal as the api: an unsafe configuration must not send alerts
        # with forgeable links any more than it may serve logins.
        for problem in problems:
            logger.error("refusing_to_start: %s", problem)
        return 1
    logger.info("alert_worker_starting", extra={"check_seconds": settings.checkin_alert_check_seconds})

    async def supervised() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        await run_loop(CheckinService(), heartbeat_file(), stop=stop)
        logger.info("alert_worker_stopped")

    asyncio.run(supervised())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
