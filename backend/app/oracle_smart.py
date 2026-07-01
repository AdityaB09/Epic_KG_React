import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import settings
from app.fhir_http import fhir_get, fhir_post_form


router = APIRouter()

SMART_AUTH_STATE: dict[str, dict[str, Any]] = {}
SMART_TOKEN_STORE: dict[str, dict[str, Any]] = {}

serializer = URLSafeSerializer(settings.SESSION_SECRET_KEY, salt="kardiogenics-oracle-smart")


def create_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def create_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def create_session_id() -> str:
    return secrets.token_urlsafe(32)


def sign_session_id(session_id: str) -> str:
    return serializer.dumps({"sid": session_id})


def unsign_session_id(value: str | None) -> str | None:
    if not value:
        return None

    try:
        data = serializer.loads(value)
        return data.get("sid")
    except BadSignature:
        return None


def get_token_for_request(request: Request) -> dict[str, Any] | None:
    session_cookie = request.cookies.get("kardiogenics_oracle_session")
    session_id = unsign_session_id(session_cookie)

    if not session_id:
        return None

    token_state = SMART_TOKEN_STORE.get(session_id)

    if not token_state:
        return None

    return token_state


async def discover_smart_configuration(fhir_base_url: str) -> dict[str, Any]:
    return await fhir_get(
        fhir_base_url.rstrip("/"),
        "/.well-known/smart-configuration",
    )


@router.get("/auth/oracle/launch")
async def oracle_launch(
    iss: str | None = Query(default=None),
    launch: str | None = Query(default=None),
):
    fhir_base_url = (iss or settings.ORACLE_FHIR_BASE_URL).rstrip("/")

    if not fhir_base_url:
        raise HTTPException(
            status_code=400,
            detail="Missing iss and ORACLE_FHIR_BASE_URL. For EHR launch, Oracle sends iss. For local testing, set ORACLE_FHIR_BASE_URL.",
        )

    if not settings.ORACLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="ORACLE_CLIENT_ID is not configured.",
        )

    smart_config = await discover_smart_configuration(fhir_base_url)

    authorization_endpoint = smart_config.get("authorization_endpoint")
    token_endpoint = smart_config.get("token_endpoint")

    if not authorization_endpoint or not token_endpoint:
        raise HTTPException(
            status_code=500,
            detail="SMART configuration missing authorization_endpoint or token_endpoint.",
        )

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    code_verifier = create_code_verifier()
    code_challenge = create_code_challenge(code_verifier)

    code_methods = smart_config.get("code_challenge_methods_supported") or []
    use_pkce = "S256" in code_methods or not code_methods

    SMART_AUTH_STATE[state] = {
        "issuer": fhir_base_url,
        "fhir_base_url": fhir_base_url,
        "launch": launch,
        "token_endpoint": token_endpoint,
        "code_verifier": code_verifier if use_pkce else None,
        "nonce": nonce,
        "created_at_epoch": time.time(),
        "expires_at_epoch": time.time() + 300,
    }

    params = {
        "response_type": "code",
        "client_id": settings.ORACLE_CLIENT_ID,
        "redirect_uri": settings.ORACLE_REDIRECT_URI,
        "scope": settings.ORACLE_SCOPES,
        "state": state,
        "aud": fhir_base_url,
        "nonce": nonce,
    }
    
    print("\n[ORACLE SMART LAUNCH DEBUG]")
    print("incoming iss:", iss)
    print("resolved fhir_base_url:", fhir_base_url)
    print("incoming launch:", launch)
    print("client_id:", settings.ORACLE_CLIENT_ID)
    print("redirect_uri:", settings.ORACLE_REDIRECT_URI)
    print("scopes:", settings.ORACLE_SCOPES)
    print("will_send_launch_param:", bool(launch))
    if launch:
        params["launch"] = launch

    if use_pkce:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    redirect_url = f"{authorization_endpoint}?{urlencode(params)}"
    print("authorization_endpoint:", authorization_endpoint)
    print("auth_url_has_launch:", "launch=" in redirect_url)
    print("[END ORACLE SMART LAUNCH DEBUG]\n")  

    return RedirectResponse(redirect_url)


@router.get("/auth/oracle/callback")
async def oracle_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    if error:
        return HTMLResponse(
            f"""
            <h2>Oracle SMART authorization failed</h2>
            <p><b>Error:</b> {error}</p>
            <p>{error_description or ""}</p>
            """,
            status_code=400,
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state.")

    auth_state = SMART_AUTH_STATE.pop(state, None)

    if not auth_state:
        raise HTTPException(status_code=400, detail="Invalid or expired SMART state.")

    if auth_state["expires_at_epoch"] < time.time():
        raise HTTPException(status_code=400, detail="Expired SMART state.")

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.ORACLE_REDIRECT_URI,
        "client_id": settings.ORACLE_CLIENT_ID,
    }

    if auth_state.get("code_verifier"):
        token_data["code_verifier"] = auth_state["code_verifier"]

    token_response = await fhir_post_form(
        auth_state["token_endpoint"],
        data=token_data,
    )

    session_id = create_session_id()

    SMART_TOKEN_STORE[session_id] = {
        "provider": "oracle",
        "fhir_base_url": auth_state["fhir_base_url"],
        "issuer": auth_state["issuer"],
        "access_token": token_response.get("access_token"),
        "refresh_token": token_response.get("refresh_token"),
        "expires_at_epoch": time.time() + int(token_response.get("expires_in", 570)),
        "scope": token_response.get("scope"),
        "patient_id": token_response.get("patient"),
        "encounter_id": token_response.get("encounter"),
        "id_token": token_response.get("id_token"),
        "created_at_epoch": time.time(),
    }

    html = """
    <h2>Oracle SMART connected</h2>
    <p>You can return to the KardioGenics React dashboard.</p>
    <p>The backend now has the Oracle SMART token in a local signed session.</p>
    <script>
      setTimeout(() => {
        window.location.href = "http://127.0.0.1:5173";
      }, 1200);
    </script>
    """

    response = HTMLResponse(html)
    response.set_cookie(
        key="kardiogenics_oracle_session",
        value=sign_session_id(session_id),
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60,
    )
    return response


@router.get("/auth/oracle/logout")
async def oracle_logout(request: Request):
    session_id = unsign_session_id(request.cookies.get("kardiogenics_oracle_session"))

    if session_id:
        SMART_TOKEN_STORE.pop(session_id, None)

    response = HTMLResponse("<h2>Oracle SMART session cleared.</h2>")
    response.delete_cookie("kardiogenics_oracle_session")
    return response