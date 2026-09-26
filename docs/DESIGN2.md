# Design 2 — Phase 2: From Prototype to a Resource Survivors Can Rely On

**As of:** 2026-09-26
**Status:** Proposal. Nothing in this document is built.
**Inputs:** `REVIEW_ENGINEERING.md` (six High defects, no test harness), `REVIEW_USER.md` (content and trust gaps seen through four people), and the existing `TODO.md`.

The repo currently labels accounts, notes, and check-ins as "Phase 2." This document renames what exists as **Phase 1 (prototype)** and defines **Phase 2** as the work that turns it into something an advocate can hand to a client. That is the only definition of "valuable resource for victims" that matters.

---

## 1. The goal in one sentence

At the end of Phase 2, a domestic-violence advocate can give a client the URL and say "this is safe to use, here is who runs it, and here is what it will and will not do for you," and every one of those three claims is true.

### What "done" means, concretely

Phase 2 is complete when all of the following hold:

1. Every High finding in `REVIEW_ENGINEERING.md` is fixed, covered by an automated test, and probed on the live site.
2. A CI run (tests + header probe + lint) blocks merges to `main`.
3. `/about`, a privacy statement, and a contact address that a real person reads exist on the site.
4. Legal counsel has reviewed the privacy statement, the emergency language, and the mandatory-reporting exposure, and their notes are resolved or accepted in writing.
5. At least one DV advocacy organization has reviewed the copy, the notes flow, and the check-in flow, and its feedback is in the repo.
6. The site leads with "in danger now / not sure / want to think," has an "Is this abuse?" page, a real safety-planning section, a "how to help someone" page, a path for male survivors, and Spanish versions of the crisis-path pages.
7. Private notes can be exported (print / PDF) client-side, and a wrong PIN can never silently fork the vault.
8. Trusted contacts get a "what to do" page, a stand-down notice, and never silently lose push.
9. A Postgres backup has been taken and restored on purpose, and someone is paged when the alert loop stops.
10. Sign-ups are either invite-gated or the site carries a plain prototype label, until items 4 and 5 are done.

If a proposed feature does not move one of those ten lines, it is not Phase 2.

---

## 2. Principles that decide trade-offs

These are inherited from Phase 1 and stay in force.

- **For every survivor, men included.** Domestic abuse happens to people of every gender and in every kind of relationship. Copy is gender-neutral by default; men get an explicit path because they are the group most likely to assume a site like this isn't for them.
- **Survivor-controlled.** Every feature is opt-in, visible, revocable, and off by default. Nothing runs hidden.
- **No false promises.** If the site cannot guarantee something (delivery of a push, a response to a message), the copy says so where the user will read it, not in a doc.
- **Zero-knowledge where possible.** Content the server does not need to read, it cannot read. Metadata the server does not need, it does not keep.
- **Free to run.** No feature may depend on a paid service. Free tiers are acceptable when the failure mode is graceful.
- **Discreet by default, invisible on request.** The site should be forgettable on a glanced-at screen, and should offer a plainer skin for people who need it.
- **Evidence-based content, verified links.** Every organization, number, and claim is checked against its source before it ships. Every model or framework cited is a real one.
- **Do the boring things.** Tests, backups, and headers are safety features for this audience. They are not chores.

---

## 3. Workstreams

Six workstreams. Each lists deliverables, acceptance criteria, and the review findings it closes. Sizes are relative: S is a day or less, M is a few days, L is a week or more.

### A. Fix-first hardening (closes engineering H1 to H5, M1 to M9)

| Deliverable | Acceptance | Size |
|---|---|---|
| Real client IP through Cloudflare (`set_real_ip_from` + `CF-Connecting-IP`), app honours proxy headers only with `TRUST_PROXY_HEADERS=true` | Two curls from different networks get separate limiter buckets; a spoofed `X-Real-IP` against bare uvicorn is ignored | S |
| nginx header snippet included in every location, with `always` | Header probe passes on `/`, `/log.html`, `/account.html`, `/checkin-invite.html`, `/api/health` | S |
| HSTS and a CSP. Move the three inline scripts to files first | CSP with no `unsafe-inline`; pages still work; probe asserts both headers | M |
| Key-check blob at PIN setup; verify on every unlock | Test: wrong PIN on an empty vault is rejected | S |
| Push device model: a device row can belong to many contacts | Test: one endpoint subscribed under two invite tokens alerts for both survivors | M |
| Lockout on `(IP, username)` with progressive delay; recovery code bypasses lock | Test: 8 failures from IP A do not block a correct login from IP B | M |
| Registration gate (`BETA_SIGNUPS_ENABLED` + invite code) or prototype banner | Decision recorded in this file; whichever is chosen is live | S |
| Advisory lock around the alert pass | Test: two concurrent passes send one alert | S |
| Dummy-hash verify on unknown username | Timing test: unknown and wrong-password paths within noise | S |
| Notes PIN minimum 12 chars with strength hint and plain-language warning | UI enforces; copy reviewed | S |
| Deadline recomputed on every schedule save while active | Test | S |
| Email as true fallback or documented "always," with repeat cadence in the alert copy | Docs and code agree | S |
| Fast hash for recovery codes | Recovery request completes in under 50 ms of CPU | S |
| Session sweep + throttled `last_seen_at` | No write on a second request within 5 minutes | S |
| Production compose without bind mount; migrations as an explicit step | `docker compose config` shows no source mount in prod | S |
| Refuse to start in production with empty `CHECKIN_TOKEN_SECRET` or default DB password | Startup test | S |
| `SameSite=Lax` | Arriving from an email link shows the logged-in state | S |

### B. Test and delivery foundation (closes M10, L3, L5)

| Deliverable | Acceptance | Size |
|---|---|---|
| `pyproject.toml` with pinned deps, `ruff`, `pytest`; Python 3.12 everywhere | `pip install -e .` and `ruff check` clean | S |
| Test suite: token sign/verify, register/login/lockout, evidence ownership, `is_overdue`, schedule math, crypto round-trip via a headless browser or a Node port of `evidence-crypto.js` | 25+ tests, green in CI | L |
| CI: tests on a throwaway Postgres, ruff, and a header probe against a built nginx | Required check on `main` | M |
| Post-deploy smoke script (curl every page, assert headers and `/api/health`) | Runs after each deploy; failure pages someone | S |
| Delete `wrangler.jsonc` and `_redirects` or document the static-only fallback | One deployment story in `ARCHITECTURE.md` | S |
| Docs consolidation: one status doc, "verified against commit" lines | `PROGRESS.md` is the only status page; others link to it | S |

### C. Trust gate (closes engineering H6, user findings for Jo and Priya)

| Deliverable | Acceptance | Size |
|---|---|---|
| `/about.html`: who runs the site, why, what it is and is not, how to reach a human | Advocate reviewer can answer "who is behind this" from the page | S |
| Privacy statement in plain language: what is stored (username, password hash, ciphertext, contact emails, push endpoints), what is not, retention, deletion, what a subpoena could and could not obtain | Reviewed by counsel | M |
| Legal review: privacy statement, emergency language, mandatory reporting, contact-email handling | Written notes in `docs/legal/`, each item resolved or accepted | External |
| Advocacy review: one organization walks the site, notes flow, check-in flow | Feedback in `docs/advocacy/`, changes tracked | External |
| Threat model: structured pass (abuser with device access, abuser with account knowledge, DB compromise, hostile trusted contact, subpoena) | `docs/THREAT_MODEL.md` with mitigations mapped to code | M |
| Contact form decision: monitored inbox with stated response window, or removal | No dead-end form on the site | S |

### D. Content that helps (user findings for Dana and Marisol)

| Deliverable | Acceptance | Size |
|---|---|---|
| Homepage rewrite: "In danger now? / Not sure what this is? / Want to think and plan?" as the first three actions | Advocate review approves copy | S |
| "Is this abuse?" page: patterns of control, non-physical examples, a short self-check, next steps | Content sourced from Hotline / NNEDV materials, cited | M |
| Safety Planning rewrite: documents to gather, leaving checklist, shared phone plan and accounts, pets, children, work, after leaving | Advocate review; each section links a verified resource | M |
| "How to help someone" page for friends, family, coworkers | Reviewed; linked from invite email and alert email | S |
| "If you get an alert" page for trusted contacts | Linked from every alert | S |
| Legal page depth: two paragraphs each on protective orders, what to bring, housing/lease breaks, custody safety, immigration remedies in plain terms | Counsel reviews for accuracy, not advice | M |
| Male survivors' path: `/for-men.html`, a men's section in Resources, neutral examples throughout | Verified resources; reviewed by an advocate with experience serving men | M |
| Spanish versions: Emergency, Resources, Safety, "Is this abuse?", Quick Exit label | Native-speaker review; `/es/` routes; language switch in header | L |
| Local finder: 211 front and center, WomensLaw state pages, Hotline's local search, a state selector that deep-links | Every state resolves to at least one verified local path | M |
| Nav cleanup: Partners out of primary nav; "Account" becomes "Notes & Check-ins"; "tracked" heading rewritten | Shipped | S |

### E. Survivor features (user findings for Marisol and Jo)

| Deliverable | Acceptance | Size |
|---|---|---|
| Notes export: print view and PDF, generated client-side from decrypted content, never sent to the server | Court-usable layout with dates; test that no plaintext leaves the browser | M |
| Photo and screenshot evidence: client-side EXIF strip, client-side encryption, size cap, stored as ciphertext blobs | Test: uploaded JPEG loses GPS tags before encryption; server stores only ciphertext | L |
| Quick Exit v2: open decoy in new tab, replace current, visible double-Escape hint, neutral title while on private pages | Manual test on iOS Safari, Android Chrome, desktop | S |
| Low-key theme: light, neutral, no glow, neutral tab title, remembered per device in `localStorage` | Toggle in header; survives reload; works without JS | M |
| Check-in reliability: alert history for the survivor, stand-down email on check-in, "push last confirmed" per contact, survivor warning when a contact's push dies | Test: check-in after an alert sends the stand-down; dead endpoint surfaces in the UI | M |
| Encrypted safety plan: the Safety Planning page becomes fillable and saves into the same zero-knowledge vault | Uses existing `EncryptedBlob`; export included | M |
| Installable PWA with offline crisis pages | Emergency and Resources load with no network after one visit | M |

### F. Operations (engineering process findings)

| Deliverable | Acceptance | Size |
|---|---|---|
| Nightly `pg_dump` to an encrypted off-host location; restore rehearsed and written up | `docs/RUNBOOK.md` has the restore steps and the date they were last run | S |
| Uptime and alert-loop heartbeat monitoring (free tier: UptimeRobot / Healthchecks.io) | Missed heartbeat pages a named person | S |
| Abuse alerting: repeated 429s from one IP notify someone | Alert fired in a test | S |
| Retention policy: default retention for inactive accounts, with warning before deletion | Written, reviewed by counsel, implemented | M |
| Incident plan: what to do if the DB is breached, who tells whom, what survivors are told | One page in `docs/` | S |
| Dependency and base-image updates on a schedule | Dependabot or a monthly task | S |

---

## 4. Sequencing

Four milestones. No dates, since this is one person's part-time project; the order is the point.

**M0 — Stop the bleeding (Workstream A, part of B).**
Fix H1 to H6. Stand up `pytest` and CI with the first tests. Take a backup and restore it. Decide and ship the sign-up gate or prototype banner. Nothing user-visible changes except the banner and the copy fixes in D that are one-liners ("tracked," nav rename).

*Exit:* live-site probe green, CI green, backup restored once, sign-up decision live.

**M1 — Earn the right to be recommended (Workstream C, rest of B).**
About page, privacy statement, contact decision, threat model. Start the legal and advocacy reviews; they run in parallel with M2 because they are external and slow.

*Exit:* a stranger can find out who runs the site and what it does with their data. Reviews requested.

**M2 — Be useful to someone who does not already know what they need (Workstream D).**
Homepage, "Is this abuse?", Safety Planning rewrite, "How to help," "If you get an alert," legal depth, local finder, Spanish crisis path. Content is the largest lever on value and the cheapest to change, so it comes before features.

*Exit:* advocate reviewer signs off on copy and content. Spanish crisis path live.

**M3 — Make the vault and the check-ins something you would stake a court date on (Workstream E, F).**
Export, photo evidence, Quick Exit v2, low-key theme, check-in reliability, encrypted safety plan, PWA. Monitoring, retention, incident plan.

*Exit:* all ten "done" conditions in section 1 hold.

---

## 5. Explicitly out of Phase 2

These are real requests. They are deferred, not rejected, unless stated.

- **Real-time location sharing.** Larger, riskier, and needs its own consent design. Phase 3 at the earliest.
- **SMS alerts.** No free option exists. Revisit only if a sponsor covers cost.
- **Partner portal, RBAC, referral workflows.** Nothing partner-facing until at least one partner exists and has asked for it.
- **Native apps.** The PWA covers install and offline.
- **Multi-factor authentication.** Recovery codes already serve as a second factor for recovery; adding MFA to login would require a device or email, both of which conflict with the shared-device threat model. Revisit with the advocacy reviewer.
- **Any public registry.** Rejected permanently, per README.
- **Full UI disguise (fake weather app).** The low-key theme and neutral titles cover most of the benefit at a fraction of the cost.
- **Server-side search over notes.** Impossible under zero-knowledge; client-side search is fine and small, and can ride along with export.

---

## 6. Risks and open decisions

| Risk / decision | Options | Recommendation |
|---|---|---|
| Sign-ups before review | Invite-gate, or visible prototype banner | Invite-gate. A banner is read by fewer people than it protects. |
| Who is "the organization" on the About page | Individual, fiscal sponsor, or a partner org | Individual with a real name and a stated intent to seek a nonprofit sponsor. Anonymity here costs more trust than it protects. |
| Photo evidence storage cost | Postgres blobs vs. object storage | Postgres `bytea`, size-capped, until volume forces otherwise. Free and inside the existing backup. |
| Spanish quality | Machine draft + native review, or professional translation | Machine draft, then a native-speaking advocate reviews. Crisis-path pages only, first. |
| Email is always sent on alert | Keep, or make push-first with email fallback | Keep always-send; a missed alert is worse than a duplicate. Fix the docs. |
| Retention default | Never delete, or delete after N months inactive with warning | 18 months inactive, warning at 12 and 17 via the in-app banner (there is no email). Counsel decides. |
| CSP vs. inline scripts | Nonces or external files | External files. Simpler, and enables caching. |

---

## 7. How this document stays true

- Each table row is a ticket in `PHASE2_PLAN.md`, which holds sequencing and status. `TODO.md` points there for Phase 2 items rather than duplicating them.
- `PROGRESS.md` remains the only "what exists now" page. This document does not track status.
- When Phase 2 closes, section 1's ten conditions are checked off here, with the commit that satisfied each, and this file is frozen.
