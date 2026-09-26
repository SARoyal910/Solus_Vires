# User Review — Solus Vires

**As of:** 2026-09-26
**Method:** Walked every page and flow on the live site and in the code as four people would experience it. No accounts were created on the live site.

The four people:

- **Dana**, on a shared phone, in the kitchen, with about ninety seconds. Wants to know if what is happening to them counts, and who to call.
- **Marisol**, who left three weeks ago and is staying with a cousin. Rebuilding. Spanish is her first language. Needs legal help and somewhere to keep a record.
- **Jo**, Marisol's cousin. Got an email saying "marisol_2 added you as a safety check-in contact." Has never heard of the site.
- **Priya**, an advocate at a county DV program, evaluating whether to hand this URL to clients.

---

## The short version

The site does something rare: it tells the truth. It does not claim to dispatch police, it says the contact form goes nowhere yet, it says the PIN cannot be recovered, and every hotline on it is real. Survivors and advocates notice that.

But right now it works best for someone who already knows what they need. It is thin for the person who does not. There is no "is this abuse?" content, no plan for leaving, no help for the friend, no Spanish, no local anything, and no page that says who is behind the site. The private notes and check-in features are the most valuable things here, and they are hidden behind a nav link called "Account."

Fix the copy and content gaps below and this becomes a site an advocate could recommend. The engineering issues are in `REVIEW_ENGINEERING.md`; this document is about whether the thing is useful.

---

## Dana: ninety seconds on a shared phone

**What works.** The homepage loads fast with no third-party junk. "This site does not dispatch emergency responders" is right there. Quick Exit is visible in the header on every page. The National DV Hotline number and the text-to-88788 option are two taps away on Emergency.

**What fails her.**

1. **Quick Exit is not quick enough.** It replaces the current page with weather.com. The back button still works, and the tab title, which currently reads "Solus Vires," has been in the history for the whole visit. The industry pattern (used by thehotline.org and most state coalitions) is to open a neutral site in a new tab *and* replace the current one, plus a visible hint that pressing Escape twice does the same. The double-Escape shortcut exists in `shared.js` but nothing on the page tells her.

2. **The design is beautiful and not discreet.** Neon cerulean and magenta on near-black, glowing orbs, a gradient headline. It looks like a crypto startup. On a phone glanced at from across a room, that is memorable. A "plain" theme (light, gray, no glow, page title "Notes" or "Weather") would matter more to Dana than any animation. `TODO.md` already scopes a disguised UI out; a low-key theme toggle is a much smaller ask than a full disguise.

3. **Nothing on the site helps her decide whether what is happening to her counts.** Every hotline page in the sector leads with "Is this abuse?" content: patterns of control, examples that are not physical, a short self-check. Solus Vires assumes she has already named it. Many people in Dana's position have not.

4. **The homepage tagline is written for a funder, not for her.** "Private by design, not by promise." "Strength, safety, and support, on your terms." She needs: "If you are in danger right now, call 911. If you cannot call, text START to 88788. If you just need to think, keep reading."

5. **Eight nav links on a phone** wrap into two rows with Partners, a roadmap page with nothing on it for her, taking a slot.

## Marisol: rebuilding, Spanish-first

**What works.** The Resources page is the best page on the site. Real organizations, real numbers, honest caveats ("not 24/7," "chat only," "not free: $65 membership"). Trans Lifeline's "never contacts police without your consent" is the kind of detail that builds trust. The Recovery page's framing ("people move back and forth, that's normal, not a setback") is genuinely kind, and the box-breathing tool works.

**What fails her.**

1. **English only.** Several listed hotlines serve 170 to 200 languages. The site that lists them serves one. A Spanish version of the emergency, resources, and safety pages is the single highest-leverage content change available. It does not need a translation platform; it needs `/es/` copies of four static pages.

2. **Everything is national.** No state selector, no shelter finder, no "find your local program." The 211 card is the only path to local help and it is buried in the tech-safety section. WomensLaw has state-by-state protective-order pages; the site links to the homepage.

3. **Safety planning is three bullets per card.** "Keep copies of key documents where they cannot be easily found" is right, but she needs the list of which documents (ID, birth certificates, immigration papers, lease, bank cards, medication, kids' school records), a leaving checklist, what to do about pets, and what to do about a shared phone plan. This page should be the deepest on the site and it is the thinnest.

4. **Private Notes are good, but she cannot get anything out.** She can write dated entries. She cannot export, print, or produce a PDF for a lawyer or a protective-order hearing. Evidence that cannot leave the vault is a diary, not evidence. There is also no photo or screenshot support, which the docs correctly flag as an EXIF risk, but for a survivor the screenshot *is* the evidence.

5. **The PIN warning is honest but arrives at the worst moment.** "If you forget it, these notes cannot be unlocked again by anyone, including us" is shown once, on setup. She should see it again before her first save, and be told to write the PIN in the same place as her recovery codes.

6. **Legal page tone is careful to the point of unhelpful.** Three "Common questions" cards each end with "go ask WomensLaw." Fine as a disclaimer, but a survivor wants two paragraphs of "what a protective order is, what it can and cannot do, what to bring" before being sent away.

## Jo: the friend who got an email

**What works.** The invite page is calm and consent-first. "You'll only receive anything if that happens." Decline is as easy as accept. The iOS "add to home screen" note appears only on iOS. The manage link works forever, so Jo can stop alerts months later.

**What fails him.**

1. **He has no idea what this site is.** The email says "Solus Vires, a private safety resource site." The invite page shows a username. There is no About page, no "who runs this," no privacy policy, and no way to verify the email is not phishing. For a stranger asked to install push notifications, that is a hard ask. An `/about.html` with a real name or organization, a plain privacy statement, and a contact address is the minimum.

2. **He is never told what to do when the alert fires.** The alert email says "consider reaching out to them directly." Jo needs a short "what to do if you get this alert" page: call them, do not confront the partner, when to call the police, what to say, what not to post. This is the most important page in the check-in feature and it does not exist.

3. **He is not told that alerts repeat every six hours, or how to know it stopped.** The alert has no "this is alert 2 of ..." and no "Marisol checked in at 3:14 pm, you can stand down." A stand-down notice is as important as the alert.

4. **If Jo is a trusted contact for two people, his push silently breaks** for whoever invited him first. (Engineering finding H4.) He will never know.

## Priya: the advocate deciding whether to recommend it

**What works.** She reads `README.md` and sees, in the project's own words, that it has not had legal review, a security audit, or advocacy input, and that the no-registry decision was deliberate and reasoned. That honesty is the best thing about the project from her chair. The zero-knowledge notes design is exactly what she would ask a vendor for.

**What stops her.**

1. **No About, no privacy policy, no terms, no organization behind it.** She cannot recommend a site to a client if she cannot say who runs it and what happens to the data. The site asks for an account and evidence and does not say this anywhere a client would find it.

2. **The contact form is a dead end that looks alive.** It says "Message received" and logs metadata to a console nobody watches. The notice above the form says as much, but a survivor in crisis reads "Send Message," not the notice. Either wire it to a monitored inbox with a stated response window, or remove the form and replace it with "we do not offer direct support; here is who does."

3. **It is live and takes sign-ups now.** Priya would want it invite-gated or clearly labelled as a prototype until the review the README promises has happened.

4. **"You're being tracked for check-ins."** That heading on `checkin.html` uses the one word every survivor has been on the wrong end of. "Your check-in schedule is on" says the same thing.

5. **No content for the people around the survivor.** Friends, parents, coworkers, and Jo. "How to help someone" is a standard page on every coalition site and is the page most likely to be shared.

6. **Missing populations she serves every week.** Immigration status (only a library for attorneys), disability, teens (Love Is Respect is listed, good), pets, and children in the home get bullet-point depth or nothing.

---

## Things that should be fixed this month, in order

| # | Change | Who it helps | Effort |
|---|--------|--------------|--------|
| 1 | About page + privacy statement + who runs this | Jo, Priya, everyone | Small |
| 2 | Quick Exit: open a decoy tab, replace current, show the double-Escape hint | Dana | Small |
| 3 | Rewrite hero copy to lead with "in danger now?" then "not sure?" then "want to think?" | Dana | Small |
| 4 | "Is this abuse?" page (patterns of control, non-physical examples, self-check) | Dana | Medium |
| 5 | Safety Planning rewrite: documents list, leaving checklist, phone plan, pets, kids | Marisol | Medium |
| 6 | Spanish versions of Emergency, Resources, Safety, and the "Is this abuse?" page | Marisol | Medium |
| 7 | Notes export: print-friendly view and PDF download, decrypted client-side only | Marisol, Priya | Medium |
| 8 | "If you get an alert" page for trusted contacts + stand-down email on check-in | Jo | Small |
| 9 | Rename "tracked" heading; move Partners out of primary nav; rename "Account" to "Notes & Check-ins" | Everyone | Tiny |
| 10 | Contact form: wire to a monitored inbox with a stated response window, or remove | Priya | Small |
| 11 | Low-key theme toggle (light, neutral, neutral tab title) | Dana | Medium |
| 12 | State/local finder: 211 front and center, WomensLaw state links, Hotline's local search | Marisol | Medium |

## Things that are fine and should not be "improved"

- The honesty about limitations. Do not soften it.
- No account required to browse. Keep it that way.
- No email or phone on signup. Keep it.
- The Recovery page tone.
- The verified-resources standard. Every new link should meet it.
- Refusing to build a registry.
