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

COOKIE_NAME = "kardiogenics_epic_session"
serializer = URLSafeSerializer(settings.SESSION_SECRET_KEY, salt="kardiogenics-epic-smart")


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
    session_cookie = request.cookies.get(COOKIE_NAME)
    session_id = unsign_session_id(session_cookie)

    if not session_id:
        return None

    return SMART_TOKEN_STORE.get(session_id)


def allowed_issuer(fhir_base_url: str) -> bool:
    issuer = fhir_base_url.rstrip("/")
    allowlist = settings.EPIC_ALLOWED_ISSUERS or [settings.EPIC_FHIR_BASE_URL.rstrip("/")]
    return issuer in allowlist


def find_oauth_uri_extension(metadata: dict[str, Any]) -> dict[str, str]:
    """
    Fallback parser for CapabilityStatement OAuth URIs.
    Preferred path is /.well-known/smart-configuration.
    """
    result: dict[str, str] = {}

    for extension in metadata.get("extension", []) or []:
        if extension.get("url") != "http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris":
            continue

        for child in extension.get("extension", []) or []:
            url_type = child.get("url")
            value_uri = child.get("valueUri")
            if url_type == "authorize" and value_uri:
                result["authorization_endpoint"] = value_uri
            if url_type == "token" and value_uri:
                result["token_endpoint"] = value_uri

    return result


async def discover_smart_configuration(fhir_base_url: str) -> dict[str, Any]:
    base = fhir_base_url.rstrip("/")

    try:
        return await fhir_get(
            base,
            "/.well-known/smart-configuration",
            extra_headers={"Epic-Client-ID": settings.EPIC_CLIENT_ID} if settings.EPIC_CLIENT_ID else None,
        )
    except Exception:
        metadata = await fhir_get(
            base,
            "/metadata",
            extra_headers={"Epic-Client-ID": settings.EPIC_CLIENT_ID} if settings.EPIC_CLIENT_ID else None,
        )
        oauth_uris = find_oauth_uri_extension(metadata)

        if not oauth_uris:
            raise HTTPException(
                status_code=500,
                detail="Epic SMART discovery failed. No SMART configuration or OAuth URIs found.",
            )

        return oauth_uris


async def start_epic_authorization(
    *,
    iss: str | None,
    launch: str | None,
    scope: str,
):
    fhir_base_url = (iss or settings.EPIC_FHIR_BASE_URL).rstrip("/")

    if not fhir_base_url:
        raise HTTPException(
            status_code=400,
            detail="Missing iss and EPIC_FHIR_BASE_URL.",
        )

    if not allowed_issuer(fhir_base_url):
        raise HTTPException(
            status_code=400,
            detail="Epic iss is not in EPIC_ALLOWED_ISSUERS.",
        )

    if not settings.EPIC_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="EPIC_CLIENT_ID is not configured.",
        )

    smart_config = await discover_smart_configuration(fhir_base_url)

    authorization_endpoint = smart_config.get("authorization_endpoint")
    token_endpoint = smart_config.get("token_endpoint")

    if not authorization_endpoint or not token_endpoint:
        raise HTTPException(
            status_code=500,
            detail="Epic SMART configuration missing authorization_endpoint or token_endpoint.",
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
        "client_id": settings.EPIC_CLIENT_ID,
        "redirect_uri": settings.EPIC_REDIRECT_URI,
        "scope": scope,
        "state": state,
        "aud": fhir_base_url,
        "nonce": nonce,
    }

    if launch:
        params["launch"] = launch

    if use_pkce:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"

    if settings.DEBUG_FHIR_LOGS:
        print("\n[KGEN EPIC SMART LAUNCH]")
        print("iss:", iss)
        print("fhir_base_url:", fhir_base_url)
        print("launch_present:", bool(launch))
        print("client_id_configured:", bool(settings.EPIC_CLIENT_ID))
        print("redirect_uri:", settings.EPIC_REDIRECT_URI)
        print("scope:", scope)
        print("authorization_endpoint:", authorization_endpoint)
        print("[END KGEN EPIC SMART LAUNCH]\n")

    return RedirectResponse(f"{authorization_endpoint}?{urlencode(params)}")


@router.get("/auth/epic/launch")
async def epic_ehr_launch(
    iss: str | None = Query(default=None),
    launch: str | None = Query(default=None),
):
    return await start_epic_authorization(
        iss=iss,
        launch=launch,
        scope=settings.EPIC_EHR_SCOPES,
    )


@router.get("/auth/epic/standalone")
async def epic_standalone_launch():
    return await start_epic_authorization(
        iss=settings.EPIC_FHIR_BASE_URL,
        launch=None,
        scope=settings.EPIC_STANDALONE_SCOPES,
    )


@router.get("/auth/epic/callback")
async def epic_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    if error:
        return HTMLResponse(
            f"""
            <h2>Epic SMART authorization failed</h2>
            <p><b>Error:</b> {error}</p>
            <p>{error_description or ""}</p>
            """,
            status_code=400,
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state.")

    auth_state = SMART_AUTH_STATE.pop(state, None)

    if not auth_state:
        raise HTTPException(status_code=400, detail="Invalid or expired Epic SMART state.")

    if auth_state["expires_at_epoch"] < time.time():
        raise HTTPException(status_code=400, detail="Expired Epic SMART state.")

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.EPIC_REDIRECT_URI,
        "client_id": settings.EPIC_CLIENT_ID,
    }

    if auth_state.get("code_verifier"):
        token_data["code_verifier"] = auth_state["code_verifier"]

    token_response = await fhir_post_form(
        auth_state["token_endpoint"],
        data=token_data,
    )

    session_id = create_session_id()

    SMART_TOKEN_STORE[session_id] = {
        "provider": "epic",
        "fhir_base_url": auth_state["fhir_base_url"],
        "issuer": auth_state["issuer"],
        "access_token": token_response.get("access_token"),
        "refresh_token": token_response.get("refresh_token"),
        "expires_at_epoch": time.time() + int(token_response.get("expires_in", 3600)),
        "scope": token_response.get("scope"),
        "patient_id": token_response.get("patient"),
        "encounter_id": token_response.get("encounter"),
        "location_id": token_response.get("location"),
        "appointment_id": token_response.get("appointment"),
        "id_token": token_response.get("id_token"),
        "created_at_epoch": time.time(),
    }

    html = f"""
    <h2>Epic SMART connected</h2>
    <p>You can return to the KardioGenics React dashboard.</p>
    <p>The backend now has the Epic SMART token in a local signed session.</p>
    <script>
      setTimeout(() => {{
        window.location.href = "{settings.EPIC_FRONTEND_REDIRECT_URL}";
      }}, 1200);
    </script>
    """

    response = HTMLResponse(html)
    response.set_cookie(
        key=COOKIE_NAME,
        value=sign_session_id(session_id),
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60,
    )
    return response


@router.get("/auth/epic/logout")
async def epic_logout(request: Request):
    session_id = unsign_session_id(request.cookies.get(COOKIE_NAME))

    if session_id:
        SMART_TOKEN_STORE.pop(session_id, None)

    response = HTMLResponse("<h2>Epic SMART session cleared.</h2>")
    response.delete_cookie(COOKIE_NAME)
    return response