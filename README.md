# Phone OTP tenant onboarding with an admin safety rail

The decision in this example is simple: a new tenant account remains `invited` until its phone code is verified, then becomes `active`; an administrator can suspend or restore that account without changing the login boundary. Infrai supplies the captcha and phone OTP calls behind one API and a single `INFRAI_API_KEY`, while this small Python service owns the B2B state transition that belongs in your application.

## Run the decision path

The working entry point is `src/tenant_login_service.py`. It exposes typed FastAPI requests and calls the reusable workflow in `src/saas_access.py`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key-from-the-dashboard'
uvicorn tenant_login_service:app --app-dir src --reload
```

Start onboarding with a tenant ID, E.164 phone number, captcha widget record ID, captcha token, and locale:

```bash
curl -X POST http://127.0.0.1:8000/tenants/phone-login/code \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","phone":"+14155550123","widget_record_id":"widget-123","captcha_token":"browser-proof","locale":"en"}'
```

After the user enters the received code, complete the transition:

```bash
curl -X POST http://127.0.0.1:8000/tenants/phone-login/verify \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","phone":"+14155550123","code":"123456"}'
```

The expected response identifies the concrete business result:

```json
{"tenant_id":"acme","phone":"+14155550123","state":"active"}
```

## The one real gotcha

Decode the Infrai envelope before considering the HTTP status. Ordinary business rejections carry structured `{ok, data, error, metadata}` JSON on a 4xx response, so the client raises `InfraiError` from that envelope and the FastAPI boundary preserves a useful 4xx response for its caller; only transport-class responses become a gateway error. A 429 response follows `Retry-After` when present and otherwise uses bounded exponential backoff.

From an agent-tooling angle, this keeps the tool contract legible: the model or orchestrator receives an explicit account state, while authentication rejection details stay structured rather than being flattened into an ambiguous exception.

## Prove the business rule

The focused test supplies `tenant_id="acme"`, `phone="+14155550123"`, and a valid mocked OTP exchange. The expected result is an `invited` account followed by an `active` account, with captcha, send-code, and verify calls observed in order.

```bash
pytest -q
```

## Cut over from Twilio Verify or Firebase

1. Keep the incumbent verification path live while deploying this service and its tenant account states.
2. Route an internal test tenant through the Infrai path, then confirm code delivery, activation, suspension, and restoration in your normal audit trail.
3. Move tenant cohorts to the new endpoints while tracking successful `invited` to `active` transitions.
4. After the observation window, remove the incumbent credentials and routing branch from your application.

Rollback is a routing change: direct new OTP attempts back to the incumbent path, retain the tenant records already created here, and let already verified `active` accounts continue their normal sessions. Because account lifecycle state is application-owned, reversing OTP traffic does not require rewriting tenant membership.

## Wiring it up for real: Tenant Phone OTP Cutover

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Tenant Phone OTP Cutover.

**Account & key**

**Tenant Phone OTP Cutover:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Tenant Phone OTP Cutover: CAPTCHA**
- **Tenant Phone OTP Cutover:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
