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
| `api` | FastAPI, **one uvicorn worker** (the alert loop ran here until 2026-10-07) | CPU, mainly Argon2 password hashing at login; in-memory rate limiter ties it to one process |
| `alert-worker` | The alert loop, every 5 minutes, in its own container from the same image (built 2026-10-07, live from the next deploy) | Serial pass over due schedules; one email API call and one push per contact |
| `db` | Postgres 16 in a container, data in the `db_data` volume | Disk and RAM on the same droplet; photos stored as `bytea`, 5 MB each, 200 per account |
| Email | Brevo, free tier | A daily sending cap shared by invites, alerts, stand-downs and contact-form mail |
| Push | Browser push services via VAPID | Free, per-device, no quota of ours |
| Backups | Nightly encrypted `pg_dump` kept on the droplet, 30 copies | Local disk; copies off the droplet are manual |

### 2.2 Capacity: estimates and the first measurements

The first column is what the architecture suggests; the "measured" rows are from `scripts/loadtest.sh` on 2026-10-07 (Stage 0 item 4), run on the owner's Mac (Apple M4 Pro, 14 cores) against a throwaway stack with one uvicorn worker, no nginx and no Cloudflare in front. The Mac is far faster than the droplet: **divide the login and alert-pass numbers by 5 to 10 for a basic droplet**, and treat the page numbers as a floor, since production serves pages from nginx behind Cloudflare, not from Python. Re-run on a droplet-sized VM before quoting them to anyone as production figures.

| Dimension | Comfortable today | Where it starts to hurt | What hurts |
|---|---|---|---|
| Public page views | Hundreds of thousands a day | Not a realistic concern | Cloudflare and static nginx |
| Registered accounts | Thousands | Tens of thousands | Postgres fine; email quota and support load are the real limits |
| Logins per second | 3–5 sustained (estimate for the droplet) | ~10 | Argon2 (t=3, 64 MiB) on one worker; everyone else waits behind it |
| Concurrent check-in schedules | Thousands | **A few hundred overdue at once** (measured, below) | The alert pass sends serially; each email is a provider round trip |
| Alert emails per day | Under the Brevo free cap | At the cap | **Alerts silently fail when the cap is reached** unless the Postmark fallback (Stage 1 item 2) is configured |
| Photos | A few hundred accounts using them | Hundreds of GB | Droplet disk, backup size and duration, `pg_dump` time |
| Database size | Tens of GB | Hundreds of GB | Backups and restores slow down before Postgres does |

**Measured 2026-10-07** (`PYTHON=.venv/bin/python scripts/loadtest.sh`, defaults):

| Test | Result | Reading |
|---|---|---|
| 500 concurrent loads of `/` from Python's static handler | 0 errors, all done in 3.1 s, p50 2.4 s, p95 2.6 s | The single worker queues them; nginx in production does this in milliseconds. A floor, not the production number |
| 500 concurrent `GET /api/health` | 0 errors, 3.0 s wall, p95 2.6 s | Same queueing; the API itself is not the cost |
| 50 concurrent logins, 50 accounts, 50 addresses | 0 errors, 1.1 s wall, p50 0.77 s, p95 1.10 s, 45 logins/s | On the droplet expect roughly 5–10/s and a p95 of several seconds under that burst. The §9 trigger (p95 above 2 s) stands |
| Alert pass, 1,000 overdue schedules, email and push stubbed with no latency | 2.0 s, 506 alerts/s | Database and application work is negligible |
| Alert pass, 200 overdue schedules, 300 ms modelled per email | 62 s, 3.2 alerts/s | **Linear in the number of overdue survivors.** 1,000 overdue at once would take about 5 minutes, the entire check interval; the heartbeat would read late and the second pass would start late |

What the measurements change:

- **The alert pass is the first real limit, not logins.** It sends one email at a time and waits for the provider each time. Today's active-schedule counts make this moot (a few hundred schedules, a few percent overdue), but it is the reason the §9 trigger for the separate worker is set at 50 active schedules and why Stage 2 should make the pass send concurrently (a small thread pool over contacts, bounded so the provider's rate limit is respected). Added to Stage 2 as item 7.
- **Logins are not the bottleneck the estimate feared** at this scale. Argon2 at these parameters costs tens of milliseconds on fast hardware; on the droplet, a burst of 50 would still clear in well under a minute.
- **Nothing failed.** No 429s from the limiters once each client had its own address, no 5xx, no connection errors at 500 concurrent.

### 2.3 Single points of failure, today

1. **The droplet.** If it dies, everything is down until a restore onto a new one. Recovery Time Objective today: a few hours of a person's attention. Recovery Point Objective: up to 24 hours (nightly backup).
2. **The one `api` process.** It serves logins *and*, until the next deploy, runs the alert loop. A restart (deploy, crash, OOM) pauses alerts for the restart's duration; a wedged process would pause them until the heartbeat (`HEALTHCHECK_PING_URL`) pages someone, if it is configured. The `alert-worker` container (Stage 1 item 5, built 2026-10-07) removes this once deployed.
3. **Brevo.** One email provider, free tier, no fallback. An outage or quota hit stops the email half of alerts; push still goes out, but only to contacts who enabled it. Postmark failover (Stage 1 item 2, built 2026-10-07) removes this once deployed with a token in `.env`.
4. **Backups on the same disk as the data.** A disk failure or a hostile actor with root takes both. The encryption protects confidentiality, not availability.
5. **The owner.** One person holds the credentials, the backup key, the pepper and the knowledge. The plan below treats this as an engineering risk, because it is.


### 2.4 Isolation from other projects

Solus Vires shares nothing with any other project the owner runs, at any stage. This is a rule, not a cost optimisation, and it is cheaper to keep than to restore:

- **Its own DigitalOcean project, ideally its own team or account.** Every resource (droplet, backups, bucket, later the database cluster and load balancer) is created there and nothing else is. Billing, API tokens, SSH keys and the people with access are separate from any hobby or client work.
- **A single-purpose droplet.** No other project's containers, cron jobs or databases on the host. Another project wanting a server gets its own small droplet.
- **Its own database, always.** Today that is the `db` container; at Stage 2 it is a managed cluster holding one database and one application user, with trusted sources limited to this project's hosts. Never a shared cluster: a managed provider's point-in-time restore rolls back every database on the cluster, a noisy neighbour's query slows the alert pass, and a leaked credential for a side project must not be able to reach survivors' data.
- **Its own vendor accounts** (Brevo, Cloudflare zone, monitoring). Where a vendor account cannot be split, the Solus Vires resources live in their own project or workspace inside it.

The reasons are the three constraints in §1. The threat model's subpoena and vendor-compromise actors reach whatever is on the same account; the privacy page's promises are only as good as the least careful thing sharing the server; and the owner's time is better spent on this project than on untangling it from another one later. Other projects may share infrastructure with each other freely; this one does not join them.

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
   - Add a nightly `scp` or `rclone` of the newest `.dump.age` to a second place (the Mac, or an object-storage bucket). The files are encrypted, so where they land matters less than that they land. Add the copy step to the cron line and have Healthchecks ping on success, so a silent failure pages you. *Built 2026-10-07:* `scripts/offsite_copy.sh` does this (size check, 30-day pruning, success and failure pings); `RUNBOOK.md` "Backups" has the one-time setup on the droplet.
3. **Rehearse the restore on a schedule.** `scripts/restore_check.sh` exists; put a calendar reminder for every quarter and record the date and duration in `RUNBOOK.md`. A backup that has not been restored is a hope, not a backup.
4. **Run one load test and write the numbers down.** From the Mac against the local preview, not production: 50 concurrent logins, 500 concurrent public page loads, an alert pass with 1,000 due schedules against a seeded database. Replace the estimates in §2.2 with what you measured. *One evening.* This tells you how far away Stage 1 really is. *Done 2026-10-07:* `scripts/loadtest.sh` (its own throwaway compose project, seeds, measures, tears down); results in §2.2. Re-run on a droplet-sized VM for production figures.
5. **Watch the email quota.** Add a line to the weekly checklist (§7): Brevo dashboard, emails sent in the last 7 days versus the cap. The alert path depends on it.
6. **Write down the bus-factor fixes.** The pepper, backup key, Brevo and DigitalOcean credentials, and Cloudflare login in a password manager vault shared with one trusted second person, with `INCIDENT_PLAN.md` naming them. Credentials are infrastructure.
7. ~~**Set the Cloudflare cache rule for static assets.**~~ **Withdrawn 2026-10-07.** A browser TTL on scripts and styles means that after a deploy, browsers run the old script under the new page for the length of the TTL; it broke the account page the day it was noticed. Cloudflare's edge still caches assets and revalidates them against nginx (cheap 304s), which is the headroom that matters. Set Browser Cache TTL to "Respect Existing Headers" (`RUNBOOK.md`, Cloudflare settings) and leave it. Revisit only with content-hashed asset names, which this static site does not have.

**Cost:** about $5–10/month over today (droplet backups, maybe a small bucket).

### Stage 1 — Hundreds of active accounts, or sign-ups opening to the public

**Trigger:** any of: sign-ups reopened after the legal and advocacy reviews (P2-B10); more than 200 accounts; more than 50 active check-in schedules; Brevo usage above half its cap in any week; the droplet above 60% CPU or 70% disk for a day.

**Goal:** remove the two failures most likely to actually happen, email quota and droplet capacity, and give the alert path a second channel.

1. **Paid Brevo plan** sized for peak alert days, not average ones. Estimate: active schedules × repeats per day (every 6 hours = 4) × contacts, for a bad day where 10% are overdue. Set a dashboard alert at 70% of the new cap.
2. **A second email provider as fallback.** The notification code (`backend/app/core/notifications.py`) sends through one client. Add a second (Postmark, Mailgun, SES; any with an HTTP API and a free or cheap tier) and fall over to it when Brevo returns an error or quota response. Record which provider carried each alert in the alert history so delivery problems are diagnosable. *Two days including tests.* This is the highest-value reliability change in the whole plan. *Built 2026-10-07, ahead of the trigger because it is cheap and the failure is silent:* Brevo primary, Postmark fallback (`POSTMARK_SERVER_TOKEN`), `checkin_alert_log.emails_via_fallback` (migration 0008), `email_failed_over` in the log. Live once deployed and a Postmark token is in `.env` (`RUNBOOK.md` "Next deploy").
3. **Resize the droplet** one step (CPU and disk together). Resizing is a few minutes of downtime; do it during the deploy window with `scripts/deploy.sh`'s backup first.
4. **Postgres housekeeping in the maintenance loop:** `VACUUM` is automatic, but add a weekly size report (table sizes, especially `evidence_attachments`) to the heartbeat ping body or a log line, so disk growth is visible before it is urgent.
5. **Separate the alert loop from the web process.** Today the loop runs inside the `api` container's lifespan. Give it its own container (same image, a different command, for example `python -m app.alert_worker`), so that a web deploy or a slow login never pauses alerts and vice versa. The advisory lock already makes this safe to run alongside the old in-process loop during the transition; afterwards set `CHECKIN_ALERT_LOOP_ENABLED=false` on `api`. *One day.* *Built 2026-10-07:* `backend/app/alert_worker.py`, the `alert-worker` service in `docker-compose.yml` with a heartbeat-file healthcheck, and the api's loop off by default in compose. Live once deployed.
6. **A staging environment that matches production.** `scripts/preview.sh` is a developer preview, not staging. A second small droplet (or the same compose stack on the Mac with a Cloudflare tunnel) running `main` before it is deployed, with the smoke test and CSP click-through pointed at it. Cheap insurance once real survivors depend on the site.
7. **Second person on call.** Not an engineer necessarily; someone who can follow `INCIDENT_PLAN.md`, restart containers, and reach you.

**Cost:** about $40–70/month (bigger droplet, paid email, small staging box).

### Stage 2 — Thousands of accounts, or a partner organisation relying on the site

**Trigger:** any of: more than 2,000 accounts; more than 500 active schedules; logins queueing (p95 login time above 2 seconds in the load test or in practice); the database above 50 GB; a restore rehearsal taking more than an hour; a partner organisation referring clients.

**Goal:** no single server, no single process, an hour's RPO, and horizontal room for the API.

1. **Managed Postgres** (DigitalOcean Managed Databases or equivalent) with point-in-time recovery. This moves the database off the application host, gives automated backups with a 7-day window and an RPO of minutes, and removes the "backups on the same disk" failure. Migration: `pg_dump` from the container, `pg_restore` into the managed instance, switch `DATABASE_URL`, redeploy. Keep the encrypted `age` dumps going as the independent second copy; a managed provider is one vendor, and the threat model's subpoena and vendor-compromise actors apply to it. *One weekend with a maintenance window.*

   **What managed Postgres buys, and what it does not.** The cheapest managed plan (about $15/month, 1 GB RAM, 10 GB disk) has *less* compute than the Postgres container already has on the droplet. That is fine: at this product's scale Postgres is light, and the plan's own estimates (§2.2) have email quota and support load as the limits long before the database. The $15 is not for RAM. It is for point-in-time recovery to any minute in the last seven days, backups that leave the application host automatically, patching and (one tier up) a standby with failover, and a database that survives losing the droplet. If the goal is more RAM or disk, resize the droplet (Stage 1 item 3), not the database plan. Until a Stage 2 trigger fires, the container plus encrypted dumps copied off the droplet (Stage 0 item 2) gives most of the durability for a fraction of the cost.

   **Why not Supabase or a similar platform.** The app has its own authentication, sessions, SQLAlchemy models and Alembic migrations; it would use Supabase only as a Postgres host, so none of the platform's auth, storage, realtime or REST layers earn their keep. Its free tier pauses projects after a week of inactivity, which for an app whose core promise is an alert loop every five minutes is an outage, so the paid tier is the floor. Every query would leave the datacenter the API runs in. And it adds a second vendor, with its own dashboard, keys and staff, to the subpoena and vendor-compromise surface the threat model already worries about. A managed Postgres in the same provider and region as the droplet, dedicated to this project (§2.4), is the right shape. Supabase and its peers are a good fit for a project that wants hosted auth and a REST API with little backend code; this is not that project.
2. **Redis for the in-memory state.** The rate limiter, login throttle and abuse counters live in process memory, which is why there is one worker. Move them to Redis (a managed instance or a container with no persistence; nothing in it needs to survive a restart, and it must never store IP history beyond the rate-limit window). Then run uvicorn with several workers, and later several `api` containers. *Three days including tests; the threat model already describes the design.*
3. **Photos out of the database into object storage.** Ciphertext blobs to a bucket (DigitalOcean Spaces or S3-compatible), keyed by attachment id, with the database keeping only the metadata row. The client already encrypts before upload, so the bucket holds nothing readable, and the bucket must be private with no public listing. Backups and restores become fast again. Migration can be lazy: new uploads to the bucket, old rows moved by a maintenance task. *A week including the export path and tests.*
4. **Two application droplets behind a load balancer**, or move the containers to a platform that does this for you (DigitalOcean App Platform, Fly.io). With the database and Redis external and the alert worker separate, `api` and `web` are stateless and can be duplicated. Deploys become rolling, so a deploy no longer takes the site down for seconds. Authenticated Origin Pulls must be configured on the load balancer or each origin.
5. **Infrastructure as code.** Terraform (or the provider's equivalent) for the droplets, load balancer, database, bucket, DNS and Cloudflare settings, so the environment can be rebuilt from the repository, and so the Cloudflare settings the CSP depends on (`RUNBOOK.md`) are enforced rather than remembered.
6. **Tighten the objectives:** RPO 1 hour, RTO 1 hour, alert delivery 99.9%.
7. **Send alerts concurrently within a pass.** The load test (§2.2) shows the pass is linear in overdue survivors because each email waits for the provider. A bounded thread pool (say 8 workers) over the contacts of a pass, with the per-survivor commit kept after that survivor's sends, cuts a 1,000-alert pass from minutes to seconds. Keep the bound below the providers' rate limits, and keep one message per contact (§5.3). *Two days including a load-test rerun.* Do it earlier than Stage 2 if the weekly checklist ever shows a pass taking longer than a minute.

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
- **Sharing a server, database cluster or cloud account with another project.** See §2.4. Cheaper by a few dollars, and it puts survivors' data one leaked side-project credential or one shared point-in-time restore away from harm.
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
