# Monitoring setup: the thirty-minute checklist

**For:** the owner, one sitting. **Written:** 2026-10-08. This is `DEPLOYPHASE2.md` Step 1 expanded into something you can follow with one hand while holding coffee. The runbook's "Monitoring" section has the same steps with more background; this file is just the order and the exact values.

When it is done, two things are true that are not true today: someone is emailed within minutes if the site stops answering, and someone is emailed within fifteen minutes if check-in alerts stop going out even while the site looks fine. The second one is the case that matters.

Pick a quiet moment for part D: the site is down for about fifteen minutes during the forced test.

---

## A. Healthchecks.io, the alert-loop heartbeat `[ ]`

**Browser, about 5 minutes.**

1. Go to healthchecks.io and choose Sign Up. Use the operator email. Confirm the email it sends you.
2. Add Check:
   - Name: `alert-loop`
   - Period: **5 minutes**
   - Grace: **10 minutes**
   - Save.
3. Add a second check:
   - Name: `backup-offsite`
   - Period: **1 day**
   - Grace: **2 hours**
   - Save. This one is for the off-site backup step (`DEPLOYPHASE2.md` Step 3) and stays grey until then.
4. Open `alert-loop` and copy its ping URL. It looks like `https://hc-ping.com/<uuid>`. Treat it like a password: anyone holding it can send fake "alive" pings. It goes in `.env` on the droplet and nowhere else.
5. Integrations: confirm email to your address is on (it is by default).

## B. UptimeRobot, is the site up `[ ]`

**Browser, about 5 minutes.**

1. Go to uptimerobot.com, Register, free plan, same email. Confirm the email.
2. Add New Monitor:
   - Monitor type: **Keyword**
   - Friendly name: `solusvires api`
   - URL: `https://solusvires.com/api/health`
   - Keyword: `ok`
   - Alert when: the keyword **does not exist**
   - Interval: **5 minutes**
3. Alert contacts: your email, ticked. Create Monitor.

## C. Wire the heartbeat into the droplet `[ ]`

**Droplet console, about 2 minutes.**

```
cd /root/solusvires
nano .env
```

Add this line at the end, pasting the URL from A4:

```
HEALTHCHECK_PING_URL=https://hc-ping.com/<the alert-loop uuid>
```

Save with Ctrl-O, Enter, then leave with Ctrl-X. Apply it:

```
docker compose up -d --wait
```

The api and alert-worker restart in a few seconds. Within five minutes the `alert-loop` check turns green on healthchecks.io. **Wait for green before part D**; otherwise the test proves nothing.

## D. Forced test `[ ]`

**Droplet console and your inbox, 15 to 20 minutes, mostly waiting.** The site is down for this part.

1. Stop both processes:
   ```
   docker compose stop api alert-worker
   ```
2. Wait and watch your inbox:
   - UptimeRobot emails "down" in about 10 minutes.
   - Healthchecks.io emails "alert-loop is down" in about 15 minutes (period plus grace).
   Both must arrive. If one hasn't after 20 minutes, go to step 3 anyway and note which was missing.
3. Start them again:
   ```
   docker compose start api alert-worker
   docker compose up -d --wait
   ```
4. Within a few minutes both services send a "back up" email, and `alert-loop` is green again. Check solusvires.com loads.

Never leave the containers stopped. If something goes wrong, step 3 is always safe.

## E. Record it `[ ]`

**Mac, 2 minutes.** In `docs/RUNBOOK.md`, under "3. Forced test", replace the placeholder row with:

| Date | What was tested | UptimeRobot email | Healthchecks email | By |
|---|---|---|---|---|
| 2026-10-08 | stopped api and alert-worker for 15 min | yes | yes | owner |

Also note the date under Scenario 4 in `docs/INCIDENT_PLAN.md`. Commit and push:

```
cd ~/Projects/solusvires
git add docs/RUNBOOK.md docs/INCIDENT_PLAN.md
git commit -m "Monitoring: forced test done 2026-10-08"
git push origin main
```

Or just tell Claude the result and it will record it.

---

## If an email didn't arrive

- **No UptimeRobot email:** on the monitor, check the keyword is `ok` and "alert when keyword does not exist" is selected, not "exists". Check the alert contact is attached to the monitor, not just created.
- **No Healthchecks email:** on the droplet, `docker compose logs --tail 30 alert-worker | grep healthcheck` should show nothing wrong; `grep HEALTHCHECK .env` must show the URL with no quotes or spaces. If the check never went green in part C, the URL is wrong.
- **Both arrived but late:** that's fine. Period plus grace is the promise, not the exact minute.

## What this does and doesn't cover

Covered: the site unreachable; the alert loop stopped, stuck or crashing. Not covered: email delivery to contacts failing while the loop runs (that's the canary account, `DEPLOYPHASE2.md` Step 5, and the Postmark fallback, Step 2). Do those next.
