import httpx
import json

from saas_access import (
    AccountState,
    InfraiPhoneClient,
    PhoneCodeRequest,
    PhoneCodeVerification,
    PhoneOnboarding,
    TenantAccounts,
)


def test_verified_otp_activates_the_invited_tenant_account() -> None:
    seen_paths: list[str] = []
    seen_bodies: list[dict[str, object]] = []

    def responder(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        seen_bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "data": {"accepted": True}})

    client = InfraiPhoneClient(
        api_key="test-key",
        transport=httpx.MockTransport(responder),
        sleep=lambda _delay: None,
    )
    workflow = PhoneOnboarding(client, TenantAccounts())

    invited = workflow.begin(
        PhoneCodeRequest(
            tenant_id="acme",
            phone="+14155550123",
            widget_record_id="widget-123",
            captcha_token="browser-proof",
        )
    )
    active = workflow.complete(
        PhoneCodeVerification(
            tenant_id="acme",
            phone="+14155550123",
            code="123456",
        )
    )

    assert invited.state is AccountState.INVITED
    assert active.state is AccountState.ACTIVE
    assert seen_paths == [
        "/v1/captcha/verify",
        "/v1/auth/phone/send_code",
        "/v1/auth/phone/verify",
    ]
    assert seen_bodies[0] == {
        "widget_record_id": "widget-123",
        "token": "browser-proof",
        "action": "phone_login",
        "score_threshold": 0.7,
    }
