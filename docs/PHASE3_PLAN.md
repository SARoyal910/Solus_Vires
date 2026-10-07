# Phase 3 Development Plan: the companion, not the hotline

**As of:** 2026-10-07, `main` after the Phase 2 close-out deploy and the `investor-ready` work (alert worker, email failover, off-site backups, load test).
**Status:** proposed. Nothing here is started. Sprints 0 and 1 can begin now; everything marked *gated* waits on the legal and advocacy reviews (P2-C3, P2-C4).
**Inputs:** `PHASE2_PLAN.md` (what Phase 2 left open), `THREAT_MODEL.md` §6 (gaps), `SCALE.md` (what breaks first and the staged plan), `DEPLOYPHASE2.md` (the owner's operational list, which runs alongside this plan and is not repeated here).
**Relationship to the other docs:** this file says *what Phase 3 builds and in what order*. `DESIGN2.md` still wins on anything it already decided. `SCALE.md` wins on infrastructure. If a ticket here would change a privacy-page claim, the privacy page changes in the same ticket or the ticket does not ship.

---

## 0. Position

Phase 3 is built around one sentence:

> **Solus Vires is the tool a survivor keeps, alongside the hotline they call.**

The National Domestic Violence Hotline and its peers have 24/7 advocates, decades of trust and national funding. We do not compete with that, and the emergency page keeps linking to them first. We build the things a crisis line structurally cannot: tools that persist between crises (the encrypted log, the safety plan, the check-in that acts when the survivor cannot), privacy that is enforced by architecture rather than policy, a product that works when the abuser holds the phone, and the friend who gets the alert treated as a user. Phase 3 finishes those four things and then proves them in public.

Everything below is judged against the three constraints in `SCALE.md` §1 (privacy, threat model, one part-time owner) and the "no false promises" rule in `DESIGN2.md` §2.

### How to read this plan

- **Ticket IDs** are `P3-<workstream><n>`. Workstreams: **G** proof, **H** evidence that holds up, **I** the friend, **J** the compromised phone, **K** partners, **L** carried-over gaps and scale.
- **Size:** S = a day or less, M = 2–4 days, L = a week or more. One part-time developer.
- **Gated** means: not started until the named review has returned and its feedback is worked through (P2-C7).
- Every code ticket ships with its test. A ticket is **Done** when merged to `main`, green in CI, deployed, and confirmed by the smoke test and, where it matters, a real device.

---

## 1. Open decisions

| # | Decision | Recommendation | Blocks | Decided |
|---|---|---|---|---|
| D10 | Publish operational evidence (uptime, alert delivery, drills) on a public page | **Yes**, monthly, numbers only, with the method stated. Proof beats marketing for a product whose promise is "we'll be there and we won't expose you." Nothing on it identifies anyone. | P3-G1 | ☐ |
| D11 | Server-side attestation of note ciphertext (the server signs "this ciphertext hash existed at time T") | **Yes, after counsel confirms it helps rather than hurts.** The server learns nothing new (it already stores the ciphertext). Must never be described as "court-admissible"; say "tamper-evident, with a verification page a lawyer can check." | P3-H1, P3-H2 | ☐ gated on P2-C3 |
| D12 | What the trusted contact may see when an alert fires | Username, alert number, hours overdue, the survivor's own pre-written note to contacts if they wrote one. **Never** location, schedule details, or other contacts. | ✅ P3-I1 | ☐ gated on P2-C4 |
| D13 | Partner referral pages: per-partner invite codes and an aggregate count, nothing else | **Yes.** No referral data flows back to the partner; they get a count. | P3-K1 | ☐ gated on P2-C4 |
| D14 | Real-time location sharing | **Still no.** Phase 4 at the earliest, with its own consent design (`DESIGN2.md` §5). The check-in alert is the product; location is a different product with a different threat model. | — | default stands |
| D15 | SMS alerts | **Still no** without the consent design and a funded sender; phone numbers are a new category of stored data (`SCALE.md` §5.3). Revisit with a partner who pays for it. | — | default stands |

---

## 2. Sprint map

```
Sprint 0  Prove it            ──►  Sprint 1  The compromised phone  ──►  Sprint 2  The friend (gated: advocacy)
(evidence page, canary record,     (sessions view, PIN change, undo,      (alert landing, what-to-do path,
 alert pass concurrency)            invite cap, Argon2id)                   contact's own note)
                                                                                  │
                                      Sprint 3  Evidence that holds up (gated: legal)  ◄───┘
                                      (attestation, verified export, lawyer's page)
                                                  │
                                      Sprint 4  Partners (gated: advocacy)
                                      (referral pages, partner codes, aggregate counts)
                                                  │
                                      Sprint 5  Close-out
                                      (review feedback round 2, public sign-ups if cleared, freeze)
```

Sprints 0 and 1 need no outside input and start now. Sprints 2 to 4 wait on the reviews, and their order can change depending on which review returns first. `DEPLOYPHASE2.md` (monitoring, Postmark, off-site backups, canary, second person) runs in parallel and is a precondition for Sprint 0's evidence page having anything to show.

---

## Sprint 0 — Prove it

**Goal:** turn the reliability work into something a survivor, a partner or an investor can check without trusting us.

| ID | Ticket | Size | Notes |
|---|---|---|---|
| P3-G1 | **Public evidence page** at `/trust.html`: pages reachable (UptimeRobot, 30 and 90 days), alert loop passes (Healthchecks), canary alerts on time (count and misses), last restore drill date and duration, backups off-site (yes/no, last copy age), independent review status, what we log (nothing per visitor) and a link to the threat model. Static HTML regenerated by hand monthly from a small script that reads the dashboards' exports; no live third-party widgets (CSP). Each number says how it was measured. | M | D10. Depends on `DEPLOYPHASE2.md` Steps 1, 3, 4, 5 for the numbers. Until they exist the page says "not yet measured", never a blank |
| P3-G2 | **Canary as code**: a `scripts/canary_check.sh` that reads the alert history for the canary account via the database (counts only) and prints the last four weeks' alerts with timestamps, so the weekly log in `SCALE.md` §5.2 is produced, not typed. | S | Runs on the droplet; output pasted into P3-G1's data |
| P3-G3 | **Alert pass sends concurrently** (`SCALE.md` Stage 2 item 7, pulled forward because the load test showed the pass is linear in overdue survivors): a bounded pool (8) over contacts within a pass, one message per contact as before, commit per survivor after that survivor's sends, bound kept under both providers' rate limits. Load test rerun with `LOAD_EMAIL_LATENCY_MS=300` and the new number written into `SCALE.md` §2.2. | M | Tests: ordering of alert numbers unchanged; a slow provider for one contact does not delay another survivor's alert past the interval |
| P3-G4 | **Weekly size and health report** in the maintenance pass: table sizes (especially `evidence_attachments`), alert-pass duration, emails via fallback this week, written as one log line and included in the heartbeat ping body if Healthchecks is configured (`SCALE.md` Stage 1 item 4). | S | No identifiers in the line |

**Exit gate:** `/trust.html` live with at least the measured items filled; the alert-pass number in `SCALE.md` §2.2 replaced by the concurrent one; the canary log produced by the script for two consecutive weeks.

---

## Sprint 1 — The compromised phone

**Goal:** make "my abuser has access to my phone" a product path, not a tip sheet, and close the account-safety gaps the threat model listed.

| ID | Ticket | Size | Notes |
|---|---|---|---|
| ✅ P3-J1 | **"Where you're signed in"** on `account.html`: count of active sessions, each with created and last-seen time and a coarse device label from the user agent (browser and OS family only), no IPs, and a "sign out everywhere else" button. | M | `THREAT_MODEL.md` §6.2. Test: the raw session token never reaches the database (§6.4) |
| ✅ P3-J2 | **Change the Notes PIN**: decrypt with the old PIN in the browser, re-encrypt every note, attachment and the safety plan under the new key, upload in one transaction with a new key-check, and refuse to proceed if any item fails to decrypt. Shows progress; large vaults take time. | L | `TODO.md` known gap. Test: a vault with notes, photos and a plan round-trips; an interrupted change leaves the old key working |
| ✅ P3-J3 | **Undo for a deleted note** (short window, client-side only): a deleted entry is held in memory for 30 seconds with an "Undo" bar before the delete request is sent. | S | `THREAT_MODEL.md` §6.2. Nothing is stored server-side for the undo |
| ✅ P3-J4 | **Daily cap on invite emails per account** (say 10), with a plain message, so one account cannot spend the email quota alerts depend on. | S | `THREAT_MODEL.md` §6.3. Test: the 11th invite in a day is refused and logged as a count |
| ✅ P3-J5 | **"If someone has access to your phone" path**: a page and a short in-app flow that walks through what the app does and does not protect on a watched device (the notes are encrypted, the browser history is not), how to use the plain view and the low-key theme, how to clear site data, how to use a different device for the check-in, and when *not* to install the app. Reviewed by the advocacy reviewer when that review happens; ships before it with the current best wording. | M | Content plus small UI. Links from the homepage "not sure what's happening" branch and from `account.html` |
| ☐ P3-J6 | **Argon2id in the browser** for the Notes key (WASM), replacing PBKDF2 at 600k iterations: faster on old phones, stronger against offline guessing of a leaked database. Migration is lazy: a vault is upgraded on its next successful unlock, with the key-check rewritten. | L | `PHASE2_PLAN.md` §5 risk. The WASM must be self-hosted (CSP, no third parties). Test: old vaults still unlock; upgraded vaults use the new parameters. **Deferred 2026-10-07, on purpose:** it means vendoring a third-party WebAssembly binary into the key-derivation path and adding `'wasm-unsafe-eval'` to the CSP, which deserves its own review rather than riding in a sprint of six other tickets. The rekey flow built for P3-J2 is the migration path: a KDF upgrade is a "PIN change" to the same PIN under new parameters, so the hard half is done |
| ✅ P3-J7 | **Tests the threat model asked for**: contact's "stop" and the survivor's contact removal. | S | `THREAT_MODEL.md` §6.4 |

**Exit gate:** a survivor can see and end their other sessions, change their PIN without losing anything, and read a reviewed path for the watched-phone case; the invite cap is live.

**Status 2026-10-07:** built and tested, except P3-J6 (deferred, see its row). `watched-phone.html` ships with the operator's wording and says on the page that the advocacy review is pending. Migrations 0009 (sessions label, invite log) and 0010 (rekey staging), so the ledger in §3 shifts: attestation becomes 0011, partners 0012, contact notes 0013.

---

## Sprint 2 — The friend (gated: advocacy review)

**Goal:** the trusted contact is a user. When the alert fires, they should know what to do in the next ten minutes.

| ID | Ticket | Size | Notes |
|---|---|---|---|
| P3-I1 | **Alert landing page with context**: the "manage alerts" link in an alert email opens a page that shows what D12 allows (username, alert number, hours overdue, the survivor's pre-written note), then the short path: try to reach them, who else to call, when to call emergency services, what not to do (do not confront the abuser, do not post). Built from `if-you-get-an-alert.html` with the alert's context filled in. | M | D12. No survivor data beyond D12's list, ever. Test: a contact token for one survivor cannot see another's context |
| ✅ P3-I2 | **The survivor's note to contacts**: an optional, encrypted-at-rest message the survivor writes in advance ("if you get this, call my sister first, don't call my mother"), decrypted server-side only at alert time for inclusion in the email and the landing page. Plainly labelled on `checkin.html` as something the server can read when an alert fires. | M | Needs its own line on the privacy page. Counsel and advocate both review the wording |
| ✅ P3-I3 | **Push for the contact's acknowledgment**: a contact can press "I've got this" on the landing page; other contacts of the same survivor see "someone is on it" on theirs (no names). Stored as a count and a timestamp per alert, nothing more. | M | Reduces duplicate panic calls to the survivor; advocate reviews whether this is wanted |
| ✅ P3-I4 | **Help-someone page as a path**: `help-someone.html` restructured into "right now", "this week", "for the long run", with the alert landing linking into the first. | S | Content |

**Exit gate:** a real alert to a real phone opens a landing page that an advocate has read and approved; the privacy page says exactly what a contact can see.

**Status 2026-10-07:** built and tested ahead of the gate; the wording on the landing page and the contact-note card is the operator's and goes to the advocacy reviewer with the rest. The note needs `CONTACT_NOTE_KEY` in `.env` (32 bytes, urlsafe base64); without it the card says the feature is off. Migration 0011, so attestation is 0012 and partners 0013.

---

## Sprint 3 — Evidence that holds up (gated: legal review)

**Goal:** turn the private log into something that changes an outcome in a protective-order hearing, without the server ever reading it.

| ID | Ticket | Size | Notes |
|---|---|---|---|
| P3-H1 | **Ciphertext attestation**: when a note, attachment or plan is saved, the server records `sha256(ciphertext)`, the server time, and a signature over both with a server key (Ed25519, rotated yearly, public keys published on `/trust.html`). Stored next to the entry; returned with it. The server learns nothing it did not already hold. | M | D11. Migration `0010` (`0009` is still the pencilled column drop from Phase 2). Test: tampering with stored ciphertext fails verification; the signature verifies against the published key |
| P3-H2 | **Verified export**: the existing client-side export (P2-E3) gains, per entry, the ciphertext hash, the attestation time and the signature, plus a final "how to verify" page with the public key and a one-paragraph method. A standalone `verify.html` lets anyone with the export and the key check it offline. Language approved by counsel; never "admissible", always "tamper-evident". | L | Test: the export still makes zero network calls; the verifier rejects an edited export |
| P3-H3 | **Lawyer's and advocate's page**: `/for-advocates.html` explaining what the log is, what the attestation does and does not prove, how to verify an export, and what a subpoena to us can and cannot obtain (from the threat model, counsel-reviewed). | S | Content |
| P3-H4 | **Retention policy** (P2-F6, moved here): inactive-account retention and the deletion schedule, as counsel advises, implemented in the maintenance pass with a warning email only if the survivor opted into one. | M | Privacy page updated in the same ticket |

**Exit gate:** counsel has read P3-H2's wording and P3-H3; a sample export verifies offline on a machine that has never seen the site.

---

## Sprint 4 — Partners (gated: advocacy review)

**Goal:** let shelters and legal-aid organisations recommend the tools without any data flowing back to them.

| ID | Ticket | Size | Notes |
|---|---|---|---|
| P3-K1 | **Partner referral pages**: `/p/<slug>.html`, one per partner, with their name, a one-line "recommended by", and invite codes that belong to that partner (codes move from `.env` to a `partner_invite_codes` table, migration `0011`). Registration with a partner code records only the partner id on the account, used for one number: how many accounts came through them. | M | D13. The partner never receives usernames or activity. Test: a partner code works, the count increments, nothing else is stored |
| P3-K2 | **Partner one-pager** (PDF and page): what the tools do, what we store, the evidence page, how to refer, how to stop referring. | S | Content; reuses `INVESTOR_PACK.md` §3 and §4 |
| P3-K3 | **Quarterly aggregate report** for partners and the public: accounts, active schedules, alerts delivered on time, canary results, in buckets, never small numbers that could identify someone. | S | Script; output goes on `/trust.html` |

**Exit gate:** one partner organisation has a live referral page and has referred at least one person; the quarterly report has run once.

---

## Sprint 5 — Close-out

| ID | Ticket | Size | Notes |
|---|---|---|---|
| P3-C1 | Work through the second round of review feedback (legal and advocacy) on everything Sprints 2 to 4 shipped. | M | |
| P3-C2 | **Open public sign-ups** (P2-B10) if both reviews allow it: `BETA_SIGNUPS_ENABLED=true`, invite codes kept for partners, the Stage 1 triggers in `SCALE.md` §9 watched weekly. | S | The `SCALE.md` Stage 1 list (paid email, bigger droplet, staging) should be done or scheduled before this flips |
| P3-C3 | Spanish pages: native-speaker review applied (P2-D8), and the new Phase 3 pages translated where they are survivor-facing. | M | |
| P3-C4 | Freeze: `DESIGN2.md` and this plan marked done; Phase 4 candidates listed (location sharing with consent design, SMS with a funded sender, partner portal if a partner asks) and not started. | S | |

---

## 3. Migration ledger

| Rev | Sprint | Change |
|---|---|---|
| 0009 | 1 | ✅ `sessions.device_label`; `invite_emails` table (P3-J1, P3-J4) |
| 0010 | 1 | ✅ `evidence_attachments.pending_*` staging columns for the PIN change (P3-J2) |
| 0011 | 2 | ✅ `checkin_schedules.contact_note` (at rest), `ack_count`, `first_ack_at` (P3-I2, P3-I3) |
| 0012 | 3 | `evidence_attestations` (entry id, kind, ciphertext hash, attested at, key id, signature) |
| 0013 | 4 | `partner_invite_codes`, `users.partner_id` (nullable) |
| later | any | drop `users.failed_login_count`, `users.locked_until` (carried from Phase 2; the model still maps them, so the model change ships a release first) |

All additive. Anything dropped ships a release after the code stops using it (`SCALE.md` §6).

---

## 4. Test plan summary

| Layer | Phase 3 additions | Where |
|---|---|---|
| Backend | attestation and verification, partner codes and counts, invite cap, sessions view without tokens or IPs, concurrent alert pass ordering, contact acks, retention sweep | `backend/tests/` |
| Client crypto | PIN change round-trip and interruption, Argon2id upgrade of an old vault, verified export makes zero network calls, offline verifier rejects edits | `tests/web/` |
| Browser | alert landing page from a real token, undo bar, sessions page, CSP click-through of every new page, `/trust.html` and `/p/<slug>.html` under the plain view | `tests/browser/` |
| Load | `scripts/loadtest.sh` after P3-G3, with modelled latency, numbers into `SCALE.md` §2.2 | Mac, then a droplet-sized VM |
| Manual (recorded) | real alert to a real phone opening P3-I1; a PIN change on a phone with photos; an export verified on a clean machine | `RUNBOOK.md` checklists |

---

## 5. Risks to this plan

| Risk | Mitigation |
|---|---|
| The reviews take months and Sprints 2 to 4 sit idle | Sprints 0 and 1 are a quarter of work on their own and need nobody; `DEPLOYPHASE2.md` runs alongside. Send the requests first (`DEPLOYPHASE2.md` Step 8) |
| Attestation is read as a legal promise | D11 wording rule: never "admissible"; counsel reviews every sentence on `/for-advocates.html` and in the export |
| The contact's note (P3-I2) is readable by the server at alert time | It is, by design, and the privacy page says so; the survivor chooses whether to write one. The alternative, the contact holding a key, fails the "a trusted contact is a person, not a service" rule |
| PIN change loses a vault halfway | P3-J2 refuses to start unless every item decrypts, uploads atomically, and the old key keeps working until the new key-check is committed |
| Public evidence page shows a bad month | That is the point. A missed objective gets an incident review (`SCALE.md` §3), and the page says what happened |
| Concurrency in the alert pass trips a provider rate limit | Bound of 8, measured against both providers' documented limits, with the fallback path covering a 429 |

---

## 6. Guardrails: what not to "improve"

- Do not add chat, a general directory, or anything the Hotline already does at national scale. Link to them.
- Do not let any Phase 3 page load a third-party script, font or widget, including for the evidence page's charts. Render numbers as text or inline SVG.
- Do not add location, SMS or a partner portal because a partner asks nicely; D14 and D15 stand until Phase 4 with their own consent designs.
- Do not store anything about the trusted contact beyond what Phase 2 already stores plus the acknowledgment count.
- Do not describe anything as court-admissible, certified or guaranteed.
- Do not open public sign-ups before both reviews return, however good the evidence page looks.

---

## 7. Summary for the owner

- Phase 3 makes the site the companion a survivor keeps: proof in public, a product for the watched phone, the friend as a user, evidence a lawyer can verify, and partners who refer without receiving data.
- Start Sprints 0 and 1 now; they need nobody else. Send the review requests this week, because Sprints 2 to 4 wait on them.
- The migration ledger reserves 0009 for the old column drop and 0010 to 0012 for Phase 3; everything stays additive.
- Nothing here changes the three constraints: privacy by architecture, the threat model first, and one part-time owner until a partner or funding changes that.
