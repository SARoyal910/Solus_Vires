# Investor and Partner Pack (working draft)

**Started:** 2026-10-07. **Owner:** Steven Royal (Omnia Royal LLC).
**Status:** draft. Every `[ ]` is a number or fact the owner fills in from the evidence it names. Do not present a line with an empty bracket.

This is the technical and operational half of a pitch: what exists, how it is run, what the evidence for "production-ready" is, what is honestly not done, and what money would buy. The product story, the people and the market belong in the deck; this document is what a technical advisor or a diligence call reads afterwards. Everything here is checkable against the repository, the live site and the dashboards named.

---

## 1. One paragraph

Solus Vires is a free, private safety and resource site for anyone being hurt by a partner or family member, for every gender, and for the people around them. It is live at solusvires.com. Beyond verified directories and safety-planning content, it offers two things most resource sites do not: a private notes and evidence log that is encrypted in the browser so the server never holds anything readable, and an opt-in "I'm OK" check-in whose missed deadline alerts trusted contacts by email and push. It is built and operated by one person, with a documented threat model, a tested backend, continuous integration on every change, encrypted backups, and a staged scaling plan with costs. Accounts are invite-only until legal and advocacy review are complete.

## 2. What is live today

From `docs/PROGRESS.md` (last verified against production 2026-10-04):

- Public pages: in danger now, is this abuse, safety planning, legal, support for men, how to help someone, if you get an alert, recovery and wellness tools, a Spanish crisis path, state-by-state help.
- Accounts with recovery codes; a PIN-locked notes and evidence log encrypted with AES-GCM in the browser; photo attachments with metadata stripped before encryption; a fillable encrypted safety plan.
- Trusted-contact check-ins: schedule, grace period, numbered repeat alerts by email and Web Push, stand-down on check-in, a survivor-visible alert history, full account deletion.
- Operations: Docker Compose on a DigitalOcean droplet behind Cloudflare with Authenticated Origin Pulls, security headers and an enforced Content-Security-Policy on every page, no access logs anywhere, encrypted nightly backups, a deploy script that backs up, migrates, waits for health and smoke-tests.
- Quality: 139 backend tests against a real Postgres, browser-side encryption tests, headless-Chrome suites including a CSP click-through of every page, all in CI on every push.

## 3. Architecture on one page

```
 visitor ──TLS──▶ Cloudflare (proxy, DDoS, TLS) ──AOP client cert──▶ nginx (static pages, /api proxy)
                                                                          │
                                                                          ▼
                                                   api: FastAPI, one worker (auth, notes, check-ins)
                                                   alert-worker: the check-in alert loop, own container
                                                                          │
                                                                          ▼
                                                   Postgres 16 (ciphertext, metadata, schedules)
                                                                          │
                                                   nightly age-encrypted pg_dump ──▶ off-site bucket
 email: Brevo, with Postmark failover         push: browser push services via VAPID
 monitoring: UptimeRobot (/api/health), Healthchecks.io (alert loop heartbeat, backup copy)
```

Design choices worth saying out loud, with where they are written down:

- **The server cannot read notes, photos or safety plans.** Encryption and decryption happen in the browser under a PIN the server never sees (`docs/ACCOUNTS_AND_NOTES.md`).
- **No third-party scripts, fonts, analytics or trackers on any page**, enforced by the Content-Security-Policy and checked in CI (`docs/THREAT_MODEL.md`, `html/privacy.html`).
- **The alert path is treated as life-safety.** It runs in its own process, pings a heartbeat after every pass, fails over between two email providers, and records per-provider delivery in the survivor's own history (`docs/SCALE.md` §5).
- **Everything is replaceable.** Each component in the diagram can be swapped or duplicated without rewriting the application (`docs/SCALE.md` §4).

## 4. Security and privacy posture

- **Threat model** (`docs/THREAT_MODEL.md`): seven actors, from an abuser holding the survivor's phone to legal compulsion and our own providers, each with the mitigations in place and the gaps still open. Several ordinary web-app features (login notification emails, MFA, audit logs) are deliberately absent because they help the attacker in this setting; the reasoning is recorded.
- **Data minimisation**: usernames are chosen to be non-identifying; no email is required for a survivor account; no IP history; alert history is counts only; contact-form messages are emailed and never stored.
- **Secrets and keys**: backup encryption key and recovery-code pepper held offline; database password rotated; production refuses to start with a placeholder secret.
- **Independent review**: *not yet done.* Legal counsel and a domestic-violence advocacy organisation (including expertise with male survivors) are being sought; request packets are drafted in `docs/legal/` and `docs/advocacy/`. A security audit is planned for Stage 3 of the scaling plan. Say this plainly; it is the most important open item.

## 5. Reliability evidence

Fill from the dashboards and the runbook tables. Each row names its source.

| Claim | Evidence | Value |
|---|---|---|
| Public pages reachable | UptimeRobot, last 30 and 90 days | `[ ]` % |
| Alert loop running | Healthchecks.io `alert-loop`, last 30 days: number of late or missed pings | `[ ]` |
| Alert delivery, end to end | Canary account weekly log (`docs/SCALE.md` §5.2), weeks green in a row | `[ ]` of `[ ]` weeks |
| Backups exist off the server | Healthchecks.io `backup-offsite`, last 30 days; newest file in the bucket | `[ ]` |
| Backups restore | Restore rehearsal table in `docs/RUNBOOK.md`: last date and duration | `[ ]` on `[ ]` |
| Recovery time objective | Timed restore to a fresh droplet | `[ ]` hours (target 4) |
| Load, measured | `scripts/loadtest.sh` 2026-10-07 on the owner's Mac (see `docs/SCALE.md` §2.2): 500 concurrent page loads 0 errors; 50 concurrent logins 0 errors, p95 1.1 s; alert pass over 1,000 due schedules 2.0 s without network | done; droplet-sized rerun `[ ]` |
| Tests on every change | GitHub Actions on `main`: backend 139, browser suites, CSP click-through | green at `[commit]` |
| Deploys without a broken page | `scripts/smoke.sh` after every deploy; incidents in `docs/INCIDENT_PLAN.md` | `[ ]` deploys, `[ ]` rollbacks |

## 6. What is honestly not done

- Legal and advocacy review (gates public sign-ups, the retention policy and the final design freeze).
- Independent security audit.
- Monitoring accounts not yet created at the time of writing (`docs/TODO.md`); the code and runbook are ready.
- One operator. A second person for incidents and a shared credential vault are the next organisational step.
- Spanish pages await a native-speaker review.
- Known product gaps: changing the notes PIN, a "where you're signed in" view, a cap on invite emails per account.

## 7. What funding buys

Costs are from `docs/SCALE.md` §4, which also gives the trigger for each stage so money is not spent early.

| Stage | Trigger | Work | Monthly cost | One-off effort |
|---|---|---|---|---|
| 0, now | invite-only | monitoring, off-site backups, restore drills, load test, canary | $5–10 over today | days, mostly done |
| 1 | sign-ups open, or 200 accounts, or 50 active schedules | paid email sized for peak alert days, email failover (built), alert worker (built), bigger droplet, staging box, second person on call | $40–70 | about a week |
| 2 | 2,000 accounts, or 500 schedules, or a partner referring clients | managed Postgres with point-in-time recovery, Redis, photos to object storage, two app hosts behind a load balancer, infrastructure as code, concurrent alert sending | $150–300 | about a month |
| 3 | partner contract or funding round | second engineer, on-call rotation, independent security audit, data-processing agreements, observability | people, not servers | ongoing |

People: the first hire that changes the risk profile is not an engineer but a second operator who can follow the incident plan. The first engineering hire is part-time and starts with Stage 2 items 1 to 3. The first external spend worth making is the security audit.

## 8. Questions a technical advisor will ask, and the answers

- *What happens when your free email tier hits its cap?* The message goes out through Postmark; the alert history records it; the log says `email_failed_over`. Before 2026-10-07 the honest answer was that alerts silently stopped.
- *What happens when the server dies?* Public pages are down until a restore; the runbook's rehearsed procedure restores onto a fresh droplet from the off-site encrypted dump. Target four hours, worst-case data loss 24 hours until Stage 2's managed database brings that to an hour.
- *Who can read a survivor's notes?* Nobody but the survivor. The server holds ciphertext; the key is derived in the browser from a PIN it never receives. A subpoena yields ciphertext.
- *What do you log about visitors?* Nothing per visitor. No access logs, no IP history, no analytics. Error logs only, without identifiers.
- *How do you deploy?* One script: backup, migrate, build, wait for every container's healthcheck, smoke-test. The api is unhealthy by design if its schema does not match the code.
- *What breaks first at scale?* The email quota and the serial alert pass, both measured and both planned for. Not the database, not the pages.
- *Why not a managed platform or Supabase?* Written down in `docs/SCALE.md` Stage 2 item 1 and §8.

## 9. Data room

Everything is in the repository unless noted.

- `docs/PROGRESS.md`: what is live. `docs/PHASE2_PLAN.md`: tickets and decisions, with a migration ledger.
- `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, `docs/SCALE.md`, `docs/RUNBOOK.md`, `docs/INCIDENT_PLAN.md`.
- `docs/REVIEW_ENGINEERING.md` and `docs/REVIEW_USER.md`: the internal reviews and what was fixed.
- `docs/legal/` and `docs/advocacy/`: the review request packets.
- Live: solusvires.com; `https://solusvires.com/api/health`; a demo account on production with an invite code (owner provides).
- Dashboards (owner grants read access): UptimeRobot, Healthchecks.io, Brevo, DigitalOcean project.
- CI: the GitHub Actions history for `main`.
