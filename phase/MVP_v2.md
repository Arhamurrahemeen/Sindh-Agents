---
project: Sindh Agents
type: build-plan
status: draft (not started)
owner: Arham
created: 2026-07-24
scope: Post-MVP-v1 phases
pairs_with: MVP_v1.md, CLAUDE.md
---

# MVP v2 — Draft

> Seeded from `MVP_v1.md`'s original P6 ("Demo-day WhatsApp flip"), demoted here
> when P6 was reassigned to Excel inventory upload. Not started. Add further
> MVP v2 phases here as they're scoped.

---

## Demo-day WhatsApp Flip *(optional but recommended)*

**Goal:** judge messages the agent from real WhatsApp on their phone. Agent replies. Pitch multiplier.

**Files touched:**
- `.env` — new values for `FEATURE_WHATSAPP`, `TWILIO_WHATSAPP_*`
- Nothing else — the three disciplines from CLAUDE.md §7.5 mean the code paths already exist.

**Prereqs (do these the night before, not on stage):**
- Twilio account created.
- WhatsApp Sandbox enabled in Twilio console.
- Sandbox number + join keyword recorded.
- `ngrok http 8000` or public backend URL configured; Twilio inbound webhook URL points to `<public>/api/widget/inbound`.
- Team's phones opted in with `join <keyword>` — verify a message flows end-to-end.

**Run (demo day, on stage):**
```bash
# 1. Restart backend with flag on
export FEATURE_WHATSAPP=true
export TWILIO_WHATSAPP_ACCOUNT_SID=ACxxx
export TWILIO_WHATSAPP_AUTH_TOKEN=xxx
export TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
export TWILIO_WHATSAPP_WEBHOOK_SECRET=xxx
uvicorn src.main:app --port 8000

# 2. Judge sends `join <keyword>` from their WhatsApp to the sandbox number
# 3. Judge sends "denim kitni hai" via WhatsApp
# 4. Agent replies via WhatsApp within seconds
# 5. On the demo laptop, dashboard shows the same conversation with channel='whatsapp'
```

**Done means:**
- [ ] Backend starts cleanly with flag+creds.
- [ ] Twilio webhook proxies inbound to `/api/widget/inbound`; handler dispatches to WhatsApp outbound channel.
- [ ] Agent reply sent via Twilio's WhatsApp send API; judge sees it in their WhatsApp thread.
- [ ] Dashboard conversation list shows a WhatsApp icon (not widget icon) on the new row.
- [ ] Audit drawer shows the same tool_calls shape — no channel-specific fields.

**If this breaks 30 minutes before demo:** flip `FEATURE_WHATSAPP=false`, restart. Widget-only demo still ships. Do not troubleshoot Twilio on stage.

**Deliberately NOT included:** production-grade Twilio (Phase 2 per `Roadmap.md`), verified business number, opt-in flow automation, message template approvals.

---

## Change log

| Date | Change | Owner |
|---|---|---|
| 2026-07-24 | Created — WhatsApp flip demoted out of `MVP_v1.md` P6 (which is now Excel inventory upload). Content moved verbatim, no changes. | Arham |
