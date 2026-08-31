from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from saas_access import (
    Account,
    AdminAccountRequest,
    InfraiError,
    InfraiPhoneClient,
    PhoneCodeRequest,
    PhoneCodeVerification,
    PhoneOnboarding,
    TenantAccounts,
)


app = FastAPI(title="Tenant phone login")
accounts = TenantAccounts()
workflow = PhoneOnboarding(InfraiPhoneClient(), accounts)


def account_view(account: Account) -> dict[str, str]:
    return {
        "tenant_id": account.tenant_id,
        "phone": account.phone,
        "state": account.state.value,
    }


@app.exception_handler(InfraiError)
async def infrai_rejection(_request: object, error: InfraiError) -> JSONResponse:
    status_code = error.status_code if 400 <= error.status_code < 500 else 502
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": error.code, "message": str(error)}},
    )


@app.post("/tenants/phone-login/code")
def begin_phone_login(request: PhoneCodeRequest) -> dict[str, str]:
    return account_view(workflow.begin(request))


@app.post("/tenants/phone-login/verify")
def complete_phone_login(request: PhoneCodeVerification) -> dict[str, str]:
    try:
        return account_view(workflow.complete(request))
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/admin/accounts/suspend")
def suspend_account(request: AdminAccountRequest) -> dict[str, str]:
    try:
        return account_view(accounts.suspend(request.tenant_id, request.phone))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/admin/accounts/restore")
def restore_account(request: AdminAccountRequest) -> dict[str, str]:
    try:
        return account_view(accounts.restore(request.tenant_id, request.phone))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
