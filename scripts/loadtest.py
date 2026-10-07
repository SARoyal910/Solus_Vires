"""HTTP half of the load test (SCALE.md Stage 0 item 4). Run by scripts/loadtest.sh.

    python scripts/loadtest.py BASE_URL --logins 50 --pages 500

Concurrent logins (one account and one simulated client address each, so
the per-IP limiter and the per-account throttle see a crowd, not one
attacker) and concurrent public page loads. Prints p50/p95/max latency,
error counts and throughput as JSON. Needs httpx (the repo's .venv has it).
"""

import argparse
import asyncio
import json
import statistics
import sys
import time

import httpx

LOAD_PASSWORD = "load-test-password-only"


def _summary(name, timings, errors, elapsed):
    timings.sort()
    pct = lambda p: round(timings[min(len(timings) - 1, int(len(timings) * p))], 3) if timings else None  # noqa: E731
    return {
        "test": name,
        "requests": len(timings) + errors,
        "errors": errors,
        "wall_seconds": round(elapsed, 2),
        "per_second": round((len(timings) + errors) / elapsed, 1) if elapsed else None,
        "p50_s": pct(0.50),
        "p95_s": pct(0.95),
        "max_s": round(max(timings), 3) if timings else None,
        "mean_s": round(statistics.fmean(timings), 3) if timings else None,
    }


async def _timed(client, method, url, **kw):
    started = time.perf_counter()
    try:
        response = await client.request(method, url, **kw)
        ok = response.status_code < 400
        detail = None if ok else response.status_code
    except httpx.HTTPError as exc:
        ok, detail = False, type(exc).__name__
    return time.perf_counter() - started, ok, detail


async def logins(base, count):
    async with httpx.AsyncClient(base_url=base, timeout=60) as client:
        started = time.perf_counter()
        results = await asyncio.gather(
            *[
                _timed(
                    client,
                    "POST",
                    "/api/auth/login",
                    json={"username": f"login-{i:04d}", "password": LOAD_PASSWORD},
                    headers={"X-Real-IP": f"10.{(i >> 16) & 255}.{(i >> 8) & 255}.{i & 255}"},
                )
                for i in range(count)
            ]
        )
        elapsed = time.perf_counter() - started
    timings = [t for t, ok, _ in results if ok]
    failures = [d for _, ok, d in results if not ok]
    out = _summary("concurrent_logins", timings, len(failures), elapsed)
    out["failure_detail"] = sorted({str(d) for d in failures})
    return out


async def pages(base, count, path="/"):
    async with httpx.AsyncClient(base_url=base, timeout=60) as client:
        started = time.perf_counter()
        results = await asyncio.gather(
            *[
                _timed(client, "GET", path, headers={"X-Real-IP": f"10.200.{(i >> 8) & 255}.{i & 255}"})
                for i in range(count)
            ]
        )
        elapsed = time.perf_counter() - started
    timings = [t for t, ok, _ in results if ok]
    failures = [d for _, ok, d in results if not ok]
    out = _summary(f"concurrent_page_loads {path}", timings, len(failures), elapsed)
    out["failure_detail"] = sorted({str(d) for d in failures})
    return out


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--logins", type=int, default=50)
    parser.add_argument("--pages", type=int, default=500)
    args = parser.parse_args()
    results = [
        await pages(args.base_url, args.pages),
        await pages(args.base_url, args.pages, "/api/health"),
        await logins(args.base_url, args.logins),
    ]
    json.dump(results, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    asyncio.run(main())
