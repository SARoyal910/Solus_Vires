# TODO

Engineering and content work is tracked ticket by ticket in `docs/PHASE2_PLAN.md` (Appendix A maps every earlier TODO item to a ticket or a deliberate deferral). What's live is in `docs/PROGRESS.md`. This file is only the short list of things waiting on the owner.

## Waiting on the owner

**After the 2026-10-04 deploy** (`main` at `2b81477` is live)
- [x] Pushed, CI green, merged to `main`, deployed 2026-10-04
- [ ] In Cloudflare, confirm Rocket Loader, Email Address Obfuscation, and Web Analytics are off, and that no rule caches HTML
- [ ] Run the checks that need a real phone (`docs/RUNBOOK.md` "Checks that need a real phone"), including a real push and a real Brevo email (P2-E6)
- [ ] Create the UptimeRobot and Healthchecks.io checks, set `HEALTHCHECK_PING_URL`, and run the forced test (P2-F2)

**Decisions**
- [ ] Pick a public contact address and a reply window, then set `CONTACT_INBOX_EMAIL` (the form is built and stays off until then; the default wording says 7 days) (P2-C5)
- [ ] Pick an address for operator alerts (`OPERATOR_ALERT_EMAIL`) and name a second person for incidents (`docs/INCIDENT_PLAN.md`)
- [ ] Decide whether "Is this abuse?" goes in the top menu (Recovery would move to the footer) (P2-D10)
- [ ] About page says the outside review "is under way", but no request has been sent yet: send the requests or change the wording
- [ ] Privacy page says backups are deleted within 30 days: keep that true when backups are copied off the droplet, or change the wording

**People to find**
- [ ] Legal counsel and a DV advocacy organization, including someone experienced with male survivors; the request packets are drafted in `docs/legal/` and `docs/advocacy/` (D6, P2-C3/C4)
- [ ] A native Spanish speaker, ideally an advocate, to review `/es/` (P2-D8)

**Housekeeping**
- [ ] Check on the droplet that access logs are off: `docker logs --since 30m solusvires_web` should show no `GET /...` lines
- [ ] Move `~/solusvires-backup-key.txt` off the Mac (password manager or USB); it's the only key that opens the backups. Keep a copy of `RECOVERY_CODE_PEPPER` with it
- [ ] Get backups off the droplet: DigitalOcean droplet backups, or periodically `scp` a `.dump.age` to the Mac
- [ ] Check the Cloudflare dashboard for a Workers or Pages project left over from the deleted `wrangler.jsonc`
- [x] On the droplet, delete the old unused copy at `/srv/solusvires` (done 2026-10-07; the live site runs from `/root/solusvires`)
- [x] One checkout again: `~/Projects/solusvires` is on `main` with `phase2` as the working branch; the extra worktree is gone (2026-10-07). The stale local `dev` branch and the merged `lane/*` branches can be deleted with `git branch -D dev lane/a lane/b lane/c` when convenient

**Blocked until the reviews come back**
- Work through the feedback (P2-C7), the retention policy (P2-F6), reopening sign-ups (P2-B10), freezing `DESIGN2.md`

**Known gaps, not planned yet** (from `docs/THREAT_MODEL.md` §6)
- A way to change the Notes PIN; a "where you're signed in" view; a cap on invite emails per account
- Cosmetic: the signed-out `/api/auth/me` check logs a 401 in the browser console (`docs/RUNBOOK.md` "Expected console noise")

## Deliberately not planned

Kept here so they aren't mistaken for forgotten. Reasons are in `docs/DESIGN2.md` §5 and `docs/PHASE2_PLAN.md` §1.

- Real-time location sharing (Phase 3 at the earliest; needs its own consent design)
- SMS alerts (no free option)
- MFA (conflicts with the shared-device threat model; revisit with the advocacy reviewer)
- Hosted CAPTCHA (third-party script; decision D7)
- Partner portal / RBAC (no partner yet)
- A full disguised UI (the planned low-key theme covers most of the benefit)
- Any public registry of alleged abusers (rejected permanently)
