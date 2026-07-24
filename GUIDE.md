# GUIDE.md — running Sindh Agents right now

Practical "how do I actually use this thing today" notes — the gotchas that
aren't obvious from `README.md` / `docs/env_setup.md` / `docs/CLAUDE.md` alone.
Read those for full setup; this file is the fast path plus the current-stage
gotchas.

---

## 1. Current stage

Build is through **P5** (Eval + Polish) of the 7-phase plan in `phase/MVP_v1.md`.
`phase/P0.md` … `phase/P5.md` are the shipped logs for each phase.

**P6 (WhatsApp flip) has not started.** The app runs on the web chat widget
only — `FEATURE_WHATSAPP=false` in `.env`. Do not expect real WhatsApp
messages to work.

---

## 2. Start the stack

```bash
cd infra
docker compose -f docker-compose.dev.yml up -d
```

(First time ever, or after a new migration lands, run the migration step
first — see `README.md`'s Docker section.)

- `db` → `localhost:5433`
- `backend` → **`localhost:8001`** (remapped from 8000 — see §5)
- `web` → `localhost:3000`

---

## 3. Logging in — there is exactly one account

There is **one seeded SME** in dev (`apps/backend/seeds/pilot_sme.py`), and
login checks "is this phone a registered SME" *before* it even looks at the
OTP (`apps/backend/src/api/auth.py:88`). Any other phone number always
returns `"Yeh number register nahi hai"` — that's not a bug, there's just no
account for it.

**The only phone number that works:**

```
+923005551234
```

Go to `http://localhost:3000/login`, enter that number, submit.

---

## 4. Getting the OTP — no real SMS is sent

`.env` has `DEV_SMS_LOG_TO_STDOUT=true`, so OTPs are **never actually sent
via Twilio** in dev — they're only written to the backend container's
stdout. `TWILIO_WHATSAPP_FROM` is blank and `FEATURE_WHATSAPP=false`, so
there's no live SMS/WhatsApp sending path active at all right now, real
credentials in `.env` notwithstanding.

Get the code:

```bash
docker logs infra-backend-1 --tail 20
# or tail live while you submit the phone number:
docker compose -f infra/docker-compose.dev.yml logs -f backend
```

Look for a line like:

```
{"level": "info", "message": "DEV_OTP: phone=+923005551234 otp=123456 expires_in=300s", ...}
```

Enter that 6-digit code on the OTP screen. It's valid for `OTP_TTL_SECONDS`
(300s / 5 min) and allows `OTP_MAX_ATTEMPTS` (5) wrong guesses before
lockout.

**To actually send real SMS instead:** flip `DEV_SMS_LOG_TO_STDOUT=false` and
supply real Twilio credentials — out of scope for local dev/demo.

---

## 5. Port 8000 vs 8001

If you see `port is already allocated` on `docker compose up`, it's usually
another local project (not Sindh Agents) already bound to 8000. Backend's
host port is mapped `8001:8000` in `infra/docker-compose.dev.yml` for this
reason — container-internal port is still 8000, only the host mapping
changed. `web` proxies to it internally via `http://backend:8000` regardless
of the host port, so this doesn't affect anything except host-side
`curl`/browser access to the API directly.

```bash
curl http://localhost:8001/health
```

---

## 6. Known gaps (not bugs to "fix" without discussion)

- **Relative dates ("kal") silently break delivery/order-timing tool
  calls.** The planner can't resolve "tomorrow" without first seeing
  `get_current_date`'s result, which hasn't run yet at planning time. Use
  explicit dates ("1 August 2026 ko") when testing those flows. Documented
  as architecture debt in `phase/P5.md`, intentionally not fixed in MVP.
- **`/conversations` misses the Lighthouse performance target** (88/100,
  target ≥90) — its JS bundle is the one screen over the 150KB budget.
- **Eval corpus is at 28/30 (93.3%)**, passing the 80% gate but not 100% —
  the 2 failing cases are the planner correctly declining to call
  `record_order_intent` without prior buyer confirmation (working as
  designed, not a bug).
- CI's `eval` job (`.github/workflows/ci.yml`) needs `GROQ_API_KEY`,
  `QDRANT_URL`, `QDRANT_API_KEY`, `COHERE_API_KEY` added as GitHub repo
  secrets before it will pass — not yet configured.

---

## 7. Where to look for more

| Question | File |
|---|---|
| Full local setup, all env vars | `docs/env_setup.md` |
| Repo conventions, invariants, stack | `docs/CLAUDE.md` |
| API routes/contracts | `docs/api-contract.md` |
| What each phase shipped | `phase/P0.md` … `phase/P5.md` |
| Eval corpus format + gate math | `docs/eval_spec.md` |
| Original 7-phase build plan | `phase/MVP_v1.md` |
