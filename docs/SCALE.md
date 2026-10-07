# Scaling and Reliability Plan

**Written:** 2026-10-07, against `main` at `be4b5de` (Phase 2 deployed 2026-10-04).
**Owner:** the site owner, with whoever is on call (`docs/INCIDENT_PLAN.md`).
**Companion docs:** `ARCHITECTURE.md` (what exists), `THREAT_MODEL.md` (what we defend against), `RUNBOOK.md` (how to operate it), `INCIDENT_PLAN.md` (what to do when it breaks).

This is the plan a CTO would hand a small team: where the system stands, what breaks first, what to do about it, and, just as important, when *not* to do anything. It is written so the owner can run it alone today and hand it to an engineer later without re-deriving it.

---

## 1. What "scale" means for this product

Most scaling plans optimise for requests per second. This product's hard requirement is different:

> **A check-in alert must reach a trusted contact, on time, every time, including on the worst day the server ever has.**

Everything else, the public pages, the notes vault, the forms, degrades gracefully: a slow page is annoying, a late alert can be dangerous. So this plan orders work by **reliability of the alert path first, data durability second, throughput third**. Several recommendations below would look over-engineered for a content site of this size; they are here because of that first line.

Three constraints shape every choice, and none of them is negotiable without a decision recorded in `PHASE2_PLAN.md` §1:

1. **Privacy.** No third-party scripts, fonts, analytics or trackers in pages. No access logs. No IP history. Any infrastructure we add must not start collecting what the privacy page says we don't collect.
2. **Threat model.** The realistic attacker often has the survivor's own device or knows their username. "Add a login notification email" style fixes that help ordinary web apps can hurt here. Read `THREAT_MODEL.md` before adding a feature in the name of reliability.
3. **Team and money.** One part-time owner today, no revenue, hosting under roughly $30 a month. Anything that needs a full-time operator or a four-figure monthly bill is out of scope until a partner organisation exists.

---

## 2. Where we are today

### 2.1 The system

One DigitalOcean droplet behind Cloudflare, running three Docker containers from `/root/solusvires`:

| Layer | What it is | Scales by |
|---|---|---|
| Cloudflare | Proxy, TLS, DDoS absorption, Authenticated Origin Pulls | Cloudflare's problem; effectively unlimited for us |
| `web` | nginx serving static `html/` and proxying `/api/` | Static files: a small VM serves thousands of pages/second. Not a bottleneck |
| `api` | FastAPI, **one uvicorn worker**, which also runs the alert loop every 5 minutes | CPU, mainly Argon2 password hashing at login; in-memory rate limiter ties it to one process |
| `db` | Postgres 16 in a container, data in the `db_data` volume | Disk and RAM on the same droplet; photos stored as `bytea`, 5 MB each, 200 per account |
| Email | Brevo, free tier | A daily sending cap shared by invites, alerts, stand-downs and contact-form mail |
| Push | Browser push services via VAPID | Free, per-device, no quota of ours |
| Backups | Nightly encrypted `pg_dump` kept on the droplet, 30 copies | Local disk; copies off the droplet are manual |

### 2.2 Honest capacity estimates

These are engineering estimates from the architecture, not load-test results. Section 4, Stage 0, includes the one load test that would replace them with numbers.

| Dimension | Comfortable today | Where it starts to hurt | What hurts |
|---|---|---|---|
| Public page views | Hundreds of thousands a day | Not a realistic concern | Cloudflare and static nginx |
| Registered accounts | Thousands | Tens of thousands | Postgres fine; email quota and support load are the real limits |
| Logins per second | 3–5 sustained | ~10 | Argon2 (t=3, 64 MiB) on one worker; everyone else waits behind it |
| Concurrent check-in schedules | Thousands | Tens of thousands | One alert pass every 5 min does the work serially; each alert is an email API call and a push |
| Alert emails per day | Under the Brevo free cap | At the cap | **Alerts silently fail when the cap is reached.** The single most likely scaling failure |
| Photos | A few hundred accounts using them | Hundreds of GB | Droplet disk, backup size and duration, `pg_dump` time |
| Database size | Tens of GB | Hundreds of GB | Backups and restores slow down before Postgres does |

### 2.3 Single points of failure, today

1. **The droplet.** If it dies, everything is down until a restore onto a new one. Recovery Time Objective today: a few hours of a person's attention. Recovery Point Objective: up to 24 hours (nightly backup).
2. **The one `api` process.** It serves logins *and* runs the alert loop. A restart (deploy, crash, OOM) pauses alerts for the restart's duration; a wedged process would pause them until the heartbeat (`HEALTHCHECK_PING_URL`) pages someone, if it is configured.
3. **Brevo.** One email provider, free tier, no fallback. An outage or quota hit stops the email half of alerts; push still goes out, but only to contacts who enabled it.
4. **Backups on the same disk as the data.** A disk failure or a hostile actor with root takes both. The encryption protects confidentiality, not availability.
5. **The owner.** One person holds the credentials, the backup key, the pepper and the knowledge. The plan below treats this as an engineering risk, because it is.

---

## 3. Targets: what "reliable enough" means

Set targets before scaling so decisions have a yardstick. These are the proposed Service Level Objectives for the next twelve months. They are deliberately modest and achievable by one person; raising them is a conscious later step.

| Objective | Target | How it is measured |
|---|---|---|
| Public pages reachable | 99.9% monthly (about 45 minutes of downtime a month) | UptimeRobot on `/` and `/api/health` |
| Alert loop running | A pass completes at least every 10 minutes, 99.9% of the time | Healthchecks.io heartbeat on `HEALTHCHECK_PING_URL` |
| Alert delivery | An overdue check-in produces its first alert within 10 minutes of the deadline, 99% of the time | Synthetic "canary" account (§5.2) plus the alert history table |
| Data durability | No more than 24 hours of data lost in the worst case (RPO 24 h), improving to 1 h at Stage 2 | Backup log; restore rehearsal |
| Recovery time | Site restored on a fresh droplet within 4 hours of deciding to (RTO 4 h) | Timed restore drill, twice a year |
| Deploy safety | No deploy breaks a page without the smoke test catching it | `scripts/smoke.sh` after every deploy; CI click-through |

When an objective is missed, the response is an incident review (`INCIDENT_PLAN.md`), not blame. When one is met for six months, consider tightening it.

---

## 4. The staged plan

Each stage lists its **trigger** (the signal that says it is time), the **work**, and the **cost**. Do not start a stage before its trigger. Premature infrastructure is the most common way small projects die: it eats the only engineer's time and adds things that can break.

### Stage 0 — Now, invite-only, under ~100 accounts

**Trigger:** you are here.
**Goal:** know when something is wrong, be able to recover, and measure instead of guess. Nothing here changes the architecture.

1. **Turn on the monitoring that already exists in the code.** UptimeRobot keyword check on `/api/health`; Healthchecks.io check with a 5-minute period and 10-minute grace, URL in `HEALTHCHECK_PING_URL`. Run the forced test in `RUNBOOK.md` "Monitoring" so you have seen a page arrive. *Half a day.*
2. **Get backups off the droplet, automatically.** Two independent copies:
   - Turn on DigitalOcean droplet backups (weekly image, a few dollars a month). This is the fast path to a whole-server restore.
   - Add a nightly `scp` or `rclone` of the newest `.dump.age` to a second place (the Mac, or an object-storage bucket). The files are encrypted, so where they land matters less than that they land. Add the copy step to the cron line and have Healthchecks ping on success, so a silent failure pages you.
3. **Rehearse the restore on a schedule.** `scripts/restore_check.sh` exists; put a calendar reminder for every quarter and record the date and duration in `RUNBOOK.md`. A backup that has not been restored is a hope, not a backup.
4. **Run one load test and write the numbers down.** From the Mac against the local preview, not production: 50 concurrent logins, 500 concurrent public page loads, an alert pass with 1,000 due schedules against a seeded database. Replace the estimates in §2.2 with what you measured. *One evening.* This tells you how far away Stage 1 really is.
5. **Watch the email quota.** Add a line to the weekly checklist (§7): Brevo dashboard, emails sent in the last 7 days versus the cap. The alert path depends on it.
6. **Write down the bus-factor fixes.** The pepper, backup key, Brevo and DigitalOcean credentials, and Cloudflare login in a password manager vault shared with one trusted second person, with `INCIDENT_PLAN.md` naming them. Credentials are infrastructure.
7. **Set the Cloudflare cache rule for static assets.** Let Cloudflare cache `.css`, `.js`, `.png`, `.svg` for an hour; never HTML (pages are `no-cache` and `/plain/` depends on it). This is free headroom for the public pages. Combine with the existing `no-cache` on HTML.

**Cost:** about $5–10/month over today (droplet backups, maybe a small bucket).

### Stage 1 — Hundreds of active accounts, or sign-ups opening to the public

**Trigger:** any of: sign-ups reopened after the legal and advocacy reviews (P2-B10); more than 200 accounts; more than 50 active check-in schedules; Brevo usage above half its cap in any week; the droplet above 60% CPU or 70% disk for a day.

**Goal:** remove the two failures most likely to actually happen, email quota and droplet capacity, and give the alert path a second channel.

1. **Paid Brevo plan** sized for peak alert days, not average ones. Estimate: active schedules × repeats per day (every 6 hours = 4) × contacts, for a bad day where 10% are overdue. Set a dashboard alert at 70% of the new cap.
2. **A second email provider as fallback.** The notification code (`backend/app/core/notifications.py`) sends through one client. Add a second (Postmark, Mailgun, SES; any with an HTTP API and a free or cheap tier) and fall over to it when Brevo returns an error or quota response. Record which provider carried each alert in the alert history so delivery problems are diagnosable. *Two days including tests.* This is the highest-value reliability change in the whole plan.
3. **Resize the droplet** one step (CPU and disk together). Resizing is a few minutes of downtime; do it during the deploy window with `scripts/deploy.sh`'s backup first.
4. **Postgres housekeeping in the maintenance loop:** `VACUUM` is automatic, but add a weekly size report (table sizes, especially `evidence_attachments`) to the heartbeat ping body or a log line, so disk growth is visible before it is urgent.
5. **Separate the alert loop from the web process.** Today the loop runs inside the `api` container's lifespan. Give it its own container (same image, a different command, for example `python -m app.alert_worker`), so that a web deploy or a slow login never pauses alerts and vice versa. The advisory lock already makes this safe to run alongside the old in-process loop during the transition; afterwards set `CHECKIN_ALERT_LOOP_ENABLED=false` on `api`. *One day.*
6. **A staging environment that matches production.** `scripts/preview.sh` is a developer preview, not staging. A second small droplet (or the same compose stack on the Mac with a Cloudflare tunnel) running `main` before it is deployed, with the smoke test and CSP click-through pointed at it. Cheap insurance once real survivors depend on the site.
7. **Second person on call.** Not an engineer necessarily; someone who can follow `INCIDENT_PLAN.md`, restart containers, and reach you.

**Cost:** about $40–70/month (bigger droplet, paid email, small staging box).

### Stage 2 — Thousands of accounts, or a partner organisation relying on the site

**Trigger:** any of: more than 2,000 accounts; more than 500 active schedules; logins queueing (p95 login time above 2 seconds in the load test or in practice); the database above 50 GB; a restore rehearsal taking more than an hour; a partner organisation referring clients.

**Goal:** no single server, no single process, an hour's RPO, and horizontal room for the API.

1. **Managed Postgres** (DigitalOcean Managed Databases or equivalent) with point-in-time recovery. This moves the database off the application host, gives automated backups with a 7-day window and an RPO of minutes, and removes the "backups on the same disk" failure. Migration: `pg_dump` from the container, `pg_restore` into the managed instance, switch `DATABASE_URL`, redeploy. Keep the encrypted `age` dumps going as the independent second copy; a managed provider is one vendor, and the threat model's subpoena and vendor-compromise actors apply to it. *One weekend with a maintenance window.*
2. **Redis for the in-memory state.** The rate limiter, login throttle and abuse counters live in process memory, which is why there is one worker. Move them to Redis (a managed instance or a container with no persistence; nothing in it needs to survive a restart, and it must never store IP history beyond the rate-limit window). Then run uvicorn with several workers, and later several `api` containers. *Three days including tests; the threat model already describes the design.*
3. **Photos out of the database into object storage.** Ciphertext blobs to a bucket (DigitalOcean Spaces or S3-compatible), keyed by attachment id, with the database keeping only the metadata row. The client already encrypts before upload, so the bucket holds nothing readable, and the bucket must be private with no public listing. Backups and restores become fast again. Migration can be lazy: new uploads to the bucket, old rows moved by a maintenance task. *A week including the export path and tests.*
4. **Two application droplets behind a load balancer**, or move the containers to a platform that does this for you (DigitalOcean App Platform, Fly.io). With the database and Redis external and the alert worker separate, `api` and `web` are stateless and can be duplicated. Deploys become rolling, so a deploy no longer takes the site down for seconds. Authenticated Origin Pulls must be configured on the load balancer or each origin.
5. **Infrastructure as code.** Terraform (or the provider's equivalent) for the droplets, load balancer, database, bucket, DNS and Cloudflare settings, so the environment can be rebuilt from the repository, and so the Cloudflare settings the CSP depends on (`RUNBOOK.md`) are enforced rather than remembered.
6. **Tighten the objectives:** RPO 1 hour, RTO 1 hour, alert delivery 99.9%.

**Cost:** roughly $150–300/month. This is the stage where the project needs either a small grant, a partner's budget, or a volunteer engineer with a few hours a week.

### Stage 3 — Tens of thousands of accounts, multiple organisations, or a legal requirement

**Trigger:** a partner contract, a funding round, or sustained Stage 2 limits.

This stage is about the organisation more than the servers: a second engineer, an on-call rotation, an independent security audit, a documented data-processing agreement with each vendor, and possibly a formal compliance regime. Technically: multi-region failover for the alert worker and database (the alert path, not the pages, justifies it), a dedicated secrets manager instead of `.env`, structured logging with privacy-preserving redaction, and a real observability stack. None of this should be designed now; the decisions depend on who the partner is and what they require. The point of listing it is to make sure Stages 0–2 do not paint it into a corner, and they do not: every component above stays replaceable.

---

## 5. The alert path, specifically

Because this is the life-safety path, it gets its own section and its own checks regardless of stage.

### 5.1 How it fails, and the defence at each stage

| Failure | Today | Stage 1 | Stage 2 |
|---|---|---|---|
| The loop stops | Heartbeat pages someone (`HEALTHCHECK_PING_URL`), once configured | Separate worker container; a web crash cannot stop it | Two workers, one lock; one region can die |
| Email quota reached | Alert fails silently to email, push still sent | Paid cap, fallback provider, dashboard alert at 70% | Same, plus delivery recorded per provider |
| Email provider down | Same as above | Fallback provider takes over | Same |
| Push endpoint dead | Pruned; survivor sees "push lost" on the check-in page | Same | Same |
| Database down | Loop skips the pass, retries in 5 min, heartbeat goes quiet | Same | Managed database with failover |
| Deploy in progress | Alerts pause for the restart (seconds) | Worker deploys separately from web | Rolling deploys, no pause |
| Clock or timezone bug | Covered by `test_checkin.py` deadline tests | Same | Same |

### 5.2 The canary

Create one real account owned by the operator with a trusted contact that is the operator's own address and a weekly interval. Let it go overdue on purpose once a week (or set the interval so it does) and confirm the alert arrives, numbered and on time, by email and by push, and that the "all clear" arrives after checking in. Record the result in the weekly checklist. This is the only check that proves the whole path end to end, from the loop through the providers to a device, and it costs two emails a week. If it ever fails, treat it as a Sev-1 under `INCIDENT_PLAN.md`.

### 5.3 What not to do to the alert path

- Don't batch alerts to save quota. Each contact gets their own message; a shared message leaks who else is a contact.
- Don't add SMS "for reliability" without the consent design in `DESIGN2.md` §5; phone numbers are a new category of stored data.
- Don't retry indefinitely into a quota wall. Fail over, record, and page the operator.

---

## 6. Reliability practices that cost nothing but discipline

These apply at every stage and are the difference between a site that is reliable and one that is merely small.

- **Every deploy through `scripts/deploy.sh`.** It backs up, migrates, waits for health, and smoke-tests. Hand-typed `docker compose up` is for emergencies only, and then only after reading the script to remember what it would have done.
- **Migrations are additive and ship a release before anything is dropped** (the expand/contract pattern). The ledger in `PHASE2_PLAN.md` §3 already schedules `0008` this way. Never deploy a column drop in the same release that stops using the column.
- **Feature flags for anything that touches the alert path.** `CHECKIN_ALERT_LOOP_ENABLED` is the model: a setting that can turn a behaviour off without a deploy.
- **CSP stays enforced.** The rollback is a one-word header rename (`RUNBOOK.md`). Resist the temptation to loosen it for a convenience library; the privacy page depends on it.
- **Dependabot PRs get merged weekly** after CI, in one batch, deployed as one. Security patches to the base image, Postgres image and Python packages are the cheapest reliability work there is.
- **Keep the test pyramid honest.** Backend tests (127), browser-side unit tests (21), five headless-Chrome suites, and a CSP click-through of every page, all in CI on every push. Any new feature arrives with its test or it is not done (`PHASE2_PLAN.md` §0). When a bug reaches production, the fix includes the test that would have caught it.
- **Logs are for errors, never for people.** When adding observability at Stage 2, structured logs must redact usernames, emails, tokens and IPs by construction, not by remembering to. The privacy page is a promise.
- **Capacity review every quarter:** disk, database size, Brevo usage, CPU, login latency, backup duration. Compare against the triggers in §4. This review is what moves you between stages, not a feeling that things are slow.
- **Drills twice a year:** a timed restore to a fresh droplet (RTO), and a "kill the api container during an alert pass" exercise to watch the lock release and the heartbeat recover.

---

## 7. Weekly and quarterly checklists

**Weekly (15 minutes)**
- UptimeRobot and Healthchecks dashboards: any incidents?
- Brevo: emails sent this week versus the cap.
- The canary alert arrived on time, email and push, and the all-clear followed.
- `df -h` and `docker system df` on the droplet: disk under 70%.
- Dependabot PRs merged and deployed, or deliberately deferred with a note.
- Newest backup file is from last night and a copy exists off the droplet.

**Quarterly (half a day)**
- Restore rehearsal: `scripts/restore_check.sh`, timed, recorded in `RUNBOOK.md`.
- Capacity review against §4 triggers; update §2.2 numbers.
- Rotate anything rotatable that has leaked or aged: Brevo API key, DigitalOcean token. Never the pepper or the check-in token secret (see `RUNBOOK.md` for why).
- Re-read `THREAT_MODEL.md` §6 gaps; promote one to a ticket.
- Check the Cloudflare settings the CSP depends on (`RUNBOOK.md`).
- Review this document: are the triggers still right, has a stage been reached?

---

## 8. Things to deliberately not do

- **Kubernetes.** Three containers and one operator do not need an orchestrator. Revisit only at Stage 3 with a team.
- **Microservices.** The alert worker split (Stage 1) is the one justified boundary. Everything else stays one FastAPI app.
- **A rewrite to serverless or a different framework.** Nothing in the scaling path requires it, and the test suite and threat model are investments in the current code.
- **Caching HTML at Cloudflare.** It breaks `/plain/`, the `no-cache` revalidation that fixed the stale-page incident, and the privacy guarantee that private pages are `no-store`.
- **Third-party monitoring scripts in pages** (real-user monitoring, error trackers). Server-side monitoring only; the CSP will block the rest, and it should.
- **A CDN or hosting change that logs visitor IPs by default** without first checking the privacy page's claims against the vendor's logging.
- **Scaling the invite gate away.** Growth is gated by the external reviews on purpose (P2-B10). This plan makes the site ready for the people those reviews allow in; it does not argue for letting them in sooner.

---

## 9. Decision table

A quick reference: when you see the signal on the left, do the thing on the right.

| Signal | Threshold | Action |
|---|---|---|
| Brevo usage | > 50% of cap in a week | Stage 1 items 1 and 2 |
| Accounts | > 200 | Begin Stage 1 |
| Active check-in schedules | > 50 | Stage 1 item 5 (separate worker) |
| Droplet CPU | > 60% for a day | Resize (Stage 1 item 3) |
| Droplet disk | > 70% | Resize now; plan Stage 2 item 3 |
| Database size | > 50 GB | Stage 2 items 1 and 3 |
| Restore rehearsal | > 1 hour | Stage 2 item 1 |
| Login p95 | > 2 s | Stage 2 item 2 |
| Canary alert | Late or missing | Sev-1 incident, today |
| Heartbeat | Quiet > 10 min | Sev-1 incident, today |
| Partner referring clients | Any | Stage 2, and schedule the Stage 3 conversation |

---

## 10. Summary for the owner

- Today the site is a well-built single server. The public pages scale further than you will need. The accounts side is fine for the people you can invite.
- The thing most likely to fail at scale is not the server, it is the **email quota behind check-in alerts**. Watch it weekly now; add a paid plan and a fallback provider as soon as sign-ups open.
- Do Stage 0 this month: monitoring on, backups off the droplet, one restore rehearsal on the calendar, one load test, and the canary account. None of it changes the architecture.
- Move to Stage 1 only when a trigger in §9 fires. Move to Stage 2 only with a partner or funding. Never do Stage 3 without a team.
- Reliability is mostly discipline: deploy through the script, keep migrations additive, merge Dependabot weekly, rehearse restores, and read the quarterly checklist.
