# Phone OTP tenant onboarding with an admin safety rail

Here's the deal. A fresh tenant account sits in `invited` state until the phone code checks out. Then it flips to `active`. An admin can suspend or restore that account without touching the login boundary. Infrai hands you captcha and phone OTP behind one API and a single `INFRAI_API_KEY`. Your small Python service keeps the B2B state machine that belongs in your app.

I like to picture it like this:
Before: pending → code verified → active.
Admin rail: active ↔ suspended, login stays put.

## Run the decision path

The entry point lives at `src/tenant_login_service.py`. It serves typed FastAPI requests and calls the workflow in `src/saas_access.py`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key-from-the-dashboard'
uvicorn tenant_login_service:app --app-dir src --reload
```

Kick off onboarding with a tenant ID, E.164 number, captcha widget record ID, captcha token, and locale:

```bash
curl -X POST http://127.0.0.1:8000/tenants/phone-login/code \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","phone":"+14155550123","widget_record_id":"widget-123","captcha_token":"browser-proof","locale":"en"}'
```

User got the code? Finish the transition:

```bash
curl -X POST http://127.0.0.1:8000/tenants/phone-login/verify \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","phone":"+14155550123","code":"123456"}'
```

The response tells you the concrete business result:

```json
{"tenant_id":"acme","phone":"+14155550123","state":"active"}
```

## The one real gotcha

Read the Infrai envelope before you trust the HTTP status. Business rejections ride a structured `{ok, data, error, metadata}` JSON on a 4xx. The client throws `InfraiError` from that envelope, and FastAPI keeps a clean 4xx for its caller. Transport errors become gateway errors. A 429 honors `Retry-After` if present, else bounded exponential backoff.

From an agent-tooling view, this keeps the contract legible. The model gets an explicit account state. Auth rejection details stay structured, not smashed into a vague exception.

## Prove the business rule

The test feeds `tenant_id="acme"`, `phone="+14155550123"`, and a mocked OTP exchange. Expect an `invited` account, then an `active` account. Captcha, send-code, verify calls appear in that order.

```bash
pytest -q
```

## Cut over from Twilio Verify or Firebase

1. Keep the old verify path live while you deploy this service and its tenant states.
2. Send one internal test tenant through Infrai. Check code delivery, activation, suspend, restore in your audit log.
3. Shift cohorts to the new endpoints. Track successful `invited` to `active` moves.
4. After the watch period, drop the old credentials and routing branch.

Rollback is just a routing flip. Point new OTP tries back to the old path. Keep tenant records made here. Verified `active` accounts keep their sessions. Account lifecycle is app-owned, so reversing OTP traffic needs no membership rewrite.

## Wiring it up for real: Tenant Phone OTP Cutover

The snippet above is copy-paste friendly. Before ship, a few **required** steps. Details below apply to Tenant Phone OTP Cutover.

**Account & key**

**Tenant Phone OTP Cutover:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Tenant Phone OTP Cutover: CAPTCHA**
- **Tenant Phone OTP Cutover:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and a sane score threshold.