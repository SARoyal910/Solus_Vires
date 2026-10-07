# TODO

Engineering and content work is tracked ticket by ticket in `docs/PHASE2_PLAN.md` (Appendix A maps every earlier TODO item to a ticket or a deliberate deferral). What's live is in `docs/PROGRESS.md`. This file is only the short list of things waiting on the owner.

## Waiting on the owner

**After the 2026-10-04 deploy** (`main` at `2b81477` is live)
- [x] Pushed, CI green, merged to `main`, deployed 2026-10-04
- [ ] In Cloudflare, confirm Rocket Loader, Email Address Obfuscation, and Web Analytics are off, and that no rule caches HTML
- [ ] Run the checks that need a real phone (`docs/RUNBOOK.md` "Checks that need a real phone"), including a real push and a real Brevo email (P2-E6)
- [ ] Create the UptimeRobot and Healthchecks.io checks, set `HEALTHCHECK_PING_URL`, and run the forced test (P2-F2)

**Next deploy** (`investor-ready` branch, once CI is green and it is merged to `main`)
- [ ] `scripts/deploy.sh` as usual: migration 0008, new `alert-worker` container; confirm `docker compose ps` shows it healthy and the api log says `checkin_alert_loop_disabled` (`docs/RUNBOOK.md` "Next deploy: alert worker...")
- [ ] Create a Postmark account, verify the sender, put `POSTMARK_SERVER_TOKEN` in `.env`, and run the one-off failover test in the runbook
- [ ] Re-run `scripts/loadtest.sh` on a droplet-sized VM (or the staging box) so `docs/SCALE.md` §2.2 has production-shaped numbers
- [ ] Fill the `[ ]` blanks in `docs/INVESTOR_PACK.md` from UptimeRobot, Healthchecks, the restore table and the canary log; it needs about four green canary weeks first

**Phase 3 Sprints 1–3 (built 2026-10-07 on the Mac, not yet deployed; `docs/PHASE3_PLAN.md`)**
- [ ] Deploy: migrations 0009–0012. Then generate and add to `.env` (same one-liner for each, in `.env.example`): `CONTACT_NOTE_KEY` (message to contacts), `ATTESTATION_PRIVATE_KEY` (signed exports). Both features are off until set. Keep a record of the attestation public key per year.
- [ ] Send `watched-phone.html`, the alert landing block on `checkin-invite.html`, the contact-note card and `help-someone.html` to the advocacy reviewer with the packet; `for-advocates.html`, `verify.html` and the export's "How to verify" wording to counsel.
- [ ] Decide `INACTIVE_ACCOUNT_RETENTION_DAYS` with counsel; until then leave it 0 and the privacy page as is.
- [ ] P3-J6 (Argon2id in the browser) is deferred on purpose; see its row in the plan.

**Decisions**
- [ ] Pick a public contact address and a reply window, then set `CONTACT_INBOX_EMAIL` (the form is built and stays off until then; the default wording says 7 days) (P2-C5)
- [ ] Pick an address for operator alerts (`OPERATOR_ALERT_EMAIL`) and name a second person for incidents (`docs/INCIDENT_PLAN.md`)
- [ ] Decide whether "Is this abuse?" goes in the top menu (Recovery would move to the footer) (P2-D10)
- [x] About page wording fixed 2026-10-07 ("we are seeking both reviews"); the requests themselves still need sending (below)
- [x] Privacy page now mentions the encrypted off-site copy; `scripts/offsite_copy.sh` prunes the bucket at 30 days so the wording stays true (2026-10-07)

**People to find**
- [ ] Legal counsel and a DV advocacy organization, including someone experienced with male survivors; the request packets are drafted in `docs/legal/` and `docs/advocacy/` (D6, P2-C3/C4)
- [ ] A native Spanish speaker, ideally an advocate, to review `/es/` (P2-D8)

**Housekeeping**
- [ ] Check on the droplet that access logs are off: `docker logs --since 30m solusvires_web` should show no `GET /...` lines
- [ ] Move `~/solusvires-backup-key.txt` off the Mac (password manager or USB); it's the only key that opens the backups. Keep a copy of `RECOVERY_CODE_PEPPER` with it
- [ ] Get backups off the droplet: turn on DigitalOcean droplet backups, create a private Spaces bucket in a Solus Vires only project, `apt install rclone`, configure the remote, add `scripts/offsite_copy.sh` to the cron line with its own Healthchecks check (`docs/RUNBOOK.md` "Backups")
- [ ] Check the Cloudflare dashboard for a Workers or Pages project left over from the deleted `wrangler.jsonc`
- [x] On the droplet, delete the old unused copy at `/srv/solusvires` (done 2026-10-07; the live site runs from `/root/solusvires`)
- [x] One checkout again: `~/Projects/solusvires` is on `main` with `phase2` as the working branch; the extra worktree is gone (2026-10-07). The stale local `dev` branch and the merged `lane/*` branches can be deleted with `git branch -D dev lane/a lane/b lane/c` when convenient

**Blocked until the reviews come back**
- Work through the feedback (P2-C7), the retention policy (P2-F6), reopening sign-ups (P2-B10), freezing `DESIGN2.md`

**Known gaps, closed 2026-10-07** (from `docs/THREAT_MODEL.md` §6; `docs/PHASE3_PLAN.md` Sprint 1)
- ~~A way to change the Notes PIN (P3-J2); a "where you're signed in" view (P3-J1); a cap on invite emails per account (P3-J4)~~ built; live from the next deploy (migrations 0009, 0010)
- Cosmetic: the signed-out `/api/auth/me` check logs a 401 in the browser console (`docs/RUNBOOK.md` "Expected console noise")

## Deliberately not planned

Kept here so they aren't mistaken for forgotten. Reasons are in `docs/DESIGN2.md` §5 and `docs/PHASE2_PLAN.md` §1.

- Real-time location sharing (Phase 4 at the earliest; needs its own consent design; `docs/PHASE3_PLAN.md` D14)
- SMS alerts (no free option; `docs/PHASE3_PLAN.md` D15)
- MFA (conflicts with the shared-device threat model; revisit with the advocacy reviewer)
- Hosted CAPTCHA (third-party script; decision D7)
- Partner portal / RBAC (no partner yet)
- A full disguised UI (the planned low-key theme covers most of the benefit)
- Any public registry of alleged abusers (rejected permanently)
