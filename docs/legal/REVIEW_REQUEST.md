# Legal review request (P2-C3)

> **DRAFT, NOT SENT.** Prepared 2026-10-02 for the owner to edit and send. Nobody has been contacted. When it goes out, record the date, the reviewer, and how they were engaged in the table at the bottom and in `docs/PHASE2_PLAN.md` (Sprint 3 exit gate). Their notes, and how each was resolved, go in this folder (P2-C7).

Who to send it to is still open (decision D6). Options worth asking: a lawyer who advises DV programs or a state DV coalition on privacy; a law school clinic (technology/privacy or family law); a pro bono program through the state bar. Ask up front whether the review creates an attorney-client relationship with Omnia Royal LLC, and what it costs, if anything.

---

## Cover note (email draft)

> **Subject:** Request for a privacy and liability review of a free domestic-violence resource site
>
> Hello [name],
>
> I run Solus Vires (https://solusvires.com), a free, independent website for people being hurt by a partner or family member, whatever their gender. I'm Steven Royal, and I run it through my company, Omnia Royal LLC. It isn't a nonprofit or an agency yet; the intent is to find a nonprofit or advocacy partner to review it and eventually help run it.
>
> The public pages are information and verified hotlines. There are also two features for people with an (invite-only) account: a private notes log that is encrypted in the person's browser, so I can't read it, and an optional "check-in" that emails or notifies people they choose if they miss one.
>
> Before opening accounts to the public I want a lawyer to review four things: the privacy statement and terms, how the site talks about emergencies, whether I have any reporting obligations, and how I handle the email addresses of the people survivors invite. I've written specific questions below and kept the materials short. I'd be grateful for written notes, even brief ones, and I'll record how each one is resolved.
>
> Could you tell me whether this is something you could take on, and on what terms?
>
> Thank you,
> Steven Royal
> [contact address]

---

## What to review

| # | Item | Where | About |
|---|---|---|---|
| 1 | Privacy statement and terms | https://solusvires.com/privacy.html (terms section added 2026-10-02, in the next deploy) | 10 min |
| 2 | About page: who runs it, what it is and isn't | https://solusvires.com/about.html | 3 min |
| 3 | Emergency language | https://solusvires.com/emergency.html, the home page, and the footer on every page | 5 min |
| 4 | Check-in feature as the survivor and the contact see it | `checkin.html` (after login), the invite page, https://solusvires.com/if-you-get-an-alert.html, and the email text in `backend/app/services/checkin.py` (quoted in an appendix on request) | 10 min |
| 5 | Legal information pages | https://solusvires.com/legal.html (protective orders, housing, custody, immigration) | 10 min |
| 6 | What the system actually stores and who can see it | `docs/THREAT_MODEL.md` §1 and §3 (A3, A5, A6) | 10 min |
| 7 | What I'd do after a breach | `docs/INCIDENT_PLAN.md` Scenario 1 | 5 min |

A reviewer account (invite code) can be provided for items 4 and the account pages.

## Questions

**A. Privacy statement and terms**
1. Is the privacy statement accurate and sufficient as written, given what the site stores (listed on the page)? Is anything missing that a privacy statement for this kind of site should say?
2. The terms are deliberately short and plain. Are they enforceable enough to be worth having? Is there anything a lawyer would insist on adding (limitation of liability, governing law, age), and can it be said in plain words?
3. Which laws or regulations apply to an LLC running a free site like this (for example state consumer privacy laws, COPPA if a minor signs up, CAN-SPAM for invitation and alert emails)? Accounts collect no name, email, phone, or age.
4. Retention: the plan is to delete accounts after 18 months of inactivity, with in-app warnings at 12 and 17 months (there is no email to warn by). Is that reasonable? Is there any reason to keep data longer or shorter?
5. Encrypted backups are kept 30 days on the server. Copies may also be kept off the server (DigitalOcean backups, a copy on the owner's computer). Does the privacy statement need to say how long those are kept?

**B. Emergency language**
6. The site says it "does not dispatch emergency responders" and "isn't an emergency service", and that check-in alerts "can be late or never arrive". Is that clear enough to avoid anyone reasonably relying on the site in an emergency? Where else should it appear?
7. Is there any exposure if a check-in alert fails to send, or a trusted contact doesn't act, and the survivor is harmed? Does anything in the feature design increase that exposure?

**C. Mandatory reporting and legal process**
8. Does the operator of a site like this have any duty to report suspected abuse (of a child, an older adult, or an adult with a disability) in any state, given that the operator can't read notes and normally sees nothing about users? Does that change if a user writes to the contact address describing abuse?
9. If served with a subpoena or court order for a user's data (for example in a custody case), what should the operator do? Should the privacy statement promise to notify the user, given there's no way to contact them?
10. If the database were breached, which breach-notification laws could apply to this data (usernames, contacts' emails, check-in times, encrypted notes)? `docs/INCIDENT_PLAN.md` currently says "ask counsel".

**D. Trusted contacts' email addresses**
11. A survivor enters a contact's email address; the site emails them an invitation, and stores the address until the survivor removes it, even if the contact never accepts. Is that acceptable? Should addresses of contacts who never respond, or who decline, be deleted after a set time?
12. Alert and invitation emails include the survivor's chosen username. Any concern there?

**E. Content**
13. The legal page explains protective orders, lease breaks, custody safety, and immigration remedies (VAWA, U visas) in plain words, labelled as information, not advice. Is the line between information and advice drawn in the right place? Anything inaccurate?
14. The site will never publish or list people accused of abuse (no registry). Survivors' private notes may name the person hurting them. Any exposure for the operator from storing encrypted notes it can't read?

**F. Structure**
15. Is running this through an LLC adequate for now, and what changes if a nonprofit partner or fiscal sponsor joins?

---

## Sent log

| Date sent | Reviewer | Engagement | Reply received | Notes file |
|---|---|---|---|---|
| — | — | — | — | — |
