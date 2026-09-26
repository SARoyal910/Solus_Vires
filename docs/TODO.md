# TODO

Engineering and content work is tracked ticket by ticket in `docs/PHASE2_PLAN.md` (Appendix A maps every earlier TODO item to a ticket or a deliberate deferral). What's live is in `docs/PROGRESS.md`. This file is only the short list of things waiting on the owner.

## Waiting on the owner

- [ ] Check on the droplet that access logs are off: `docker logs --since 30m solusvires_web` should show no `GET /...` lines
- [ ] Move `~/solusvires-backup-key.txt` off the Mac (password manager or USB); it's the only key that opens the backups
- [ ] Get backups off the droplet: DigitalOcean droplet backups, or periodically `scp` a `.dump.age` to the Mac
- [ ] Pick a public contact address (e.g. a new site-only mailbox) so the contact form and About page can use it (P2-C5)
- [ ] Decide whether "Is this abuse?" goes in the top menu (Recovery would move to the footer), then deploy with the cache fix
- [ ] Find a native Spanish speaker, ideally an advocate, to review `/es/` (P2-D8)
- [ ] Reach out to legal counsel and a DV advocacy organization, including someone experienced with male survivors (D6, P2-C3/C4)

## Deliberately not planned

Kept here so they aren't mistaken for forgotten. Reasons are in `docs/DESIGN2.md` §5 and `docs/PHASE2_PLAN.md` §1.

- Real-time location sharing (Phase 3 at the earliest; needs its own consent design)
- SMS alerts (no free option)
- MFA (conflicts with the shared-device threat model; revisit with the advocacy reviewer)
- Hosted CAPTCHA (third-party script; decision D7)
- Partner portal / RBAC (no partner yet)
- A full disguised UI (the planned low-key theme covers most of the benefit)
- Any public registry of alleged abusers (rejected permanently)
