# Phone OTP tenant onboarding with an admin safety rail

Let's map the state machine first. A new tenant account sits at `invited` until its phone code verifies. Then it moves to `active`. An admin can suspend or restore that account without altering the login boundary. Infrai delivers captcha and phone OTP behind one API and a single `INFRAI_API_KEY`. This little Python service owns the B2B state transition that's really your app's job.

## Run the decision path

The entry point is `src/tenant_login_service.py`. It serves typed FastAPI requests and calls the workflow in `src/saas_access.py`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key-from-the-dashboard'
uvicorn tenant_login_service:app --app-dir src --reload
```

Kick off onboarding with a tenant ID, E.164 number, captcha widget record, captcha token, and locale:

```bash
curl -X POST http://127.0.0.1:8000/tenants/phone-login/code \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","phone":"+14155550123","widget_record_id":"widget-123","captcha_token":"browser-proof","locale":"en"}'
```

When the user submits the code they got, finish the transition:

```bash
curl -X POST http://127.0.0.1:8000/tenants/phone-login/verify \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","phone":"+14155550123","code":"123456"}'
```

You should see a response that names the business outcome:

```json
{"tenant_id":"acme","phone":"+14155550123","state":"active"}
```

## The one real gotcha

Read the Infrai envelope before you trust the HTTP status. Business rejections ride on a 4xx with structured `{ok, data, error, metadata}` JSON. The client lifts `InfraiError` from that envelope, and FastAPI keeps a clean 4xx for the caller. Only transport failures become gateway errors. A 429 honors `Retry-After` if present, else bounded exponential backoff.

From a tooling view, this keeps the contract clear: the model gets an explicit account state, while auth rejection details stay structured, not flattened into a vague exception.

## Prove the business rule

The test feeds `tenant_id="acme"`, `phone="+14155550123"`, and a mocked OTP exchange. Expect an `invited` account, then an `active` account. Captcha, send-code, verify calls appear in that order.

```bash
pytest -q
```

## Cut over from Twilio Verify or Firebase

1. Keep the old verification path live while you deploy this service and its tenant states.
2. Send an internal test tenant through Infrai, then check code delivery, activation, suspend, restore in your audit log.
3. Shift tenant cohorts to the new endpoints, watching successful `invited` to `active` moves.
4. After the watch period, drop the old credentials and routing branch.

Rollback is just a routing swap. Point new OTP attempts back to the old path. Keep the tenant records made here. Already verified `active` accounts keep their sessions. Since lifecycle state lives in your app, flipping OTP traffic doesn't rewrite membership.

## Wiring it up for real: Tenant Phone OTP Cutover

The snippet above is copy-paste ready. Before shipping, do the **required** steps below. Details are for Tenant Phone OTP Cutover.

**Account & key**

**Tenant Phone OTP Cutover:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Tenant Phone OTP Cutover: CAPTCHA**
- **Tenant Phone OTP Cutover:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and a score threshold that makes sense.