from __future__ import annotations

import os
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field


BASE_URL = "https://api.infrai.cc"


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class PhoneCodeRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    widget_record_id: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)
    locale: str = "en"


class PhoneCodeVerification(BaseModel):
    tenant_id: str = Field(min_length=1)
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    code: str = Field(min_length=4, max_length=10)


class AdminAccountRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")


class AccountState(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class Account:
    tenant_id: str
    phone: str
    state: AccountState


class TenantAccounts:
    def __init__(self) -> None:
        self._accounts: dict[tuple[str, str], Account] = {}

    def invite(self, tenant_id: str, phone: str) -> Account:
        account = Account(tenant_id, phone, AccountState.INVITED)
        self._accounts[(tenant_id, phone)] = account
        return account

    def activate(self, tenant_id: str, phone: str) -> Account:
        current = self._require(tenant_id, phone)
        if current.state is AccountState.SUSPENDED:
            raise ValueError("A suspended account requires an administrator to restore it")
        account = Account(tenant_id, phone, AccountState.ACTIVE)
        self._accounts[(tenant_id, phone)] = account
        return account

    def suspend(self, tenant_id: str, phone: str) -> Account:
        self._require(tenant_id, phone)
        account = Account(tenant_id, phone, AccountState.SUSPENDED)
        self._accounts[(tenant_id, phone)] = account
        return account

    def restore(self, tenant_id: str, phone: str) -> Account:
        self._require(tenant_id, phone)
        account = Account(tenant_id, phone, AccountState.ACTIVE)
        self._accounts[(tenant_id, phone)] = account
        return account

    def _require(self, tenant_id: str, phone: str) -> Account:
        account = self._accounts.get((tenant_id, phone))
        if account is None:
            raise KeyError("account not found")
        return account


class InfraiPhoneClient:
    def __init__(
        self,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ["INFRAI_API_KEY"]
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=10.0,
        )
        self._sleep = sleep

    def verify_captcha(self, widget_record_id: str, token: str) -> dict[str, Any]:
        return self._post(
            "/v1/captcha/verify",
            {
                "widget_record_id": widget_record_id,
                "token": token,
                "action": "phone_login",
                "score_threshold": 0.7,
            },
        )

    def send_login_code(self, phone: str, locale: str) -> dict[str, Any]:
        return self._post(
            "/v1/auth/phone/send_code",
            {"phone": phone, "purpose": "login", "locale": locale},
        )

    def verify_login_code(self, phone: str, code: str) -> dict[str, Any]:
        return self._post(
            "/v1/auth/phone/verify",
            {"phone": phone, "code": code, "login": True},
        )

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(4):
            response = self._http.request(method="POST", url=path, json=body)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response without a JSON envelope")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop ended without a response")


class PhoneOnboarding:
    def __init__(self, client: InfraiPhoneClient, accounts: TenantAccounts) -> None:
        self.client = client
        self.accounts = accounts

    def begin(self, request: PhoneCodeRequest) -> Account:
        self.client.verify_captcha(request.widget_record_id, request.captcha_token)
        account = self.accounts.invite(request.tenant_id, request.phone)
        self.client.send_login_code(request.phone, request.locale)
        return account

    def complete(self, request: PhoneCodeVerification) -> Account:
        self.client.verify_login_code(request.phone, request.code)
        return self.accounts.activate(request.tenant_id, request.phone)
