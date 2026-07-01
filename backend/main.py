import asyncio
import json
from typing import Any
import hashlib
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.normalizer import FIELD_LABELS, now_iso, to_dashboard_frame
from app.oracle_smart import get_token_for_request, router as oracle_smart_router
from app.providers import (
    fetch_provider_medications,
    fetch_provider_observations,
    test_provider_status,
)


app = FastAPI(title="KardioGenics FHIR Streaming Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(oracle_smart_router)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "provider": settings.FHIR_PROVIDER,
        "pollSeconds": settings.POLL_SECONDS,
        "fallbackDemoData": settings.USE_FALLBACK_DEMO_DATA,
        "firelyBaseUrl": settings.FIRELY_BASE_URL,
        "oracleMode": settings.ORACLE_MODE,
        "oracleBaseUrlConfigured": bool(settings.ORACLE_FHIR_BASE_URL),
        "oracleClientIdConfigured": bool(settings.ORACLE_CLIENT_ID),
    }


@app.get("/api/fhir/status")
async def fhir_status(
    provider: str = Query(default=settings.FHIR_PROVIDER),
):
    return await test_provider_status(provider)


@app.get("/api/fhir/oracle/status")
async def oracle_status(request: Request):
    token_state = get_token_for_request(request)

    return await test_provider_status(
        "oracle",
        access_token=token_state.get("access_token") if token_state else None,
        fhir_base_url=token_state.get("fhir_base_url") if token_state else None,
    )


@app.get("/api/fhir/oracle/session")
async def oracle_session_debug(request: Request):
    token_state = get_token_for_request(request)

    if not token_state:
        return {
            "hasOracleSession": False,
            "message": "No Oracle SMART session cookie found. Complete Oracle launch in this same browser."
        }

    return {
        "hasOracleSession": True,
        "provider": token_state.get("provider"),
        "fhirBaseUrl": token_state.get("fhir_base_url"),
        "hasAccessToken": bool(token_state.get("access_token")),
        "hasRefreshToken": bool(token_state.get("refresh_token")),
        "patientIdFromToken": token_state.get("patient_id"),
        "encounterIdFromToken": token_state.get("encounter_id"),
        "scope": token_state.get("scope"),
        "expiresAtEpoch": token_state.get("expires_at_epoch"),
    }



# @app.get("/api/firely/raw")
# async def raw_firely_observations(patient_id: str | None = Query(default=None)):
#     return await fetch_provider_observations("firely", patient_id)


# @app.get("/api/firely/latest")
# async def latest_firely_frame(
#     patient_id: str | None = Query(default=None),
#     debug: bool = Query(default=False),
# ):
#     bundle = await fetch_provider_observations("firely", patient_id)
#     return to_dashboard_frame(
#         bundle,
#         provider="firely-public-sandbox",
#         include_debug=debug,
#     )


# @app.get("/api/firely/debug/latest")
# async def latest_firely_debug_frame(patient_id: str | None = Query(default=None)):
#     bundle = await fetch_provider_observations("firely", patient_id)
#     return to_dashboard_frame(
#         bundle,
#         provider="firely-public-sandbox",
#         include_debug=True,
#     )


@app.get("/api/fhir/latest")
async def latest_fhir_frame(
    request: Request,
    provider: str = Query(default=settings.FHIR_PROVIDER),
    patient_id: str | None = Query(default=None),
    debug: bool = Query(default=False),
):
    token_state = get_token_for_request(request) if provider == "oracle" else None

    effective_patient_id = resolve_patient_id(
        provider=provider,
        requested_patient_id=patient_id,
        token_state=token_state,
    )

    access_token = token_state.get("access_token") if token_state else None
    fhir_base_url = token_state.get("fhir_base_url") if token_state else None

    observation_bundle = await fetch_provider_observations(
        provider,
        effective_patient_id,
        access_token=access_token,
        fhir_base_url=fhir_base_url,
    )

    medication_resources = await fetch_provider_medications(
        provider,
        effective_patient_id,
        access_token=access_token,
        fhir_base_url=fhir_base_url,
    )

    return to_dashboard_frame(
        observation_bundle,
        provider=provider_label(provider),
        include_debug=debug,
        medication_resources=medication_resources,
    )


# @app.get("/api/firely/stream")
# async def stream_firely_frame(
#     request: Request,
#     patient_id: str | None = Query(default=None),
#     debug: bool = Query(default=False),
# ):
#     # Old Firely route kept for compatibility.
#     return make_streaming_response(
#         request=request,
#         provider="firely",
#         patient_id=patient_id,
#         debug=debug,
#     )

@app.get("/api/firely/raw")
async def raw_firely_observations():
    return {
        "ok": False,
        "message": "Firely is disabled. Use Oracle via /api/stream or /api/fhir/latest?provider=oracle."
    }


@app.get("/api/firely/latest")
async def latest_firely_frame():
    return {
        "ok": False,
        "message": "Firely is disabled. Use Oracle via /api/fhir/latest?provider=oracle."
    }


@app.get("/api/firely/debug/latest")
async def latest_firely_debug_frame():
    return {
        "ok": False,
        "message": "Firely is disabled. Use Oracle via /api/fhir/latest?provider=oracle&debug=true."
    }


@app.get("/api/firely/stream")
async def stream_firely_frame():
    return {
        "ok": False,
        "message": "Firely is disabled. Use Oracle via /api/stream?debug=true."
    }
    
    
    
    
@app.get("/api/stream")
async def stream_fhir_frame(
    request: Request,
    debug: bool = Query(default=False),
):
    return make_streaming_response(
        request=request,
        provider="oracle",
        patient_id=None,
        debug=debug,
    )


def make_streaming_response(
    *,
    request: Request,
    provider: str,
    patient_id: str | None,
    debug: bool,
):
    async def event_generator():
        last_payload = None
        last_oracle_hash = None

        while True:
            try:
                token_state = get_token_for_request(request) if provider == "oracle" else None

                effective_patient_id = resolve_patient_id(
                    provider=provider,
                    requested_patient_id=patient_id,
                    token_state=token_state,
                )

                access_token = token_state.get("access_token") if token_state else None
                fhir_base_url = token_state.get("fhir_base_url") if token_state else None

                observation_bundle = await fetch_provider_observations(
                    provider,
                    effective_patient_id,
                    access_token=access_token,
                    fhir_base_url=fhir_base_url,
                )

                medication_resources = await fetch_provider_medications(
                    provider,
                    effective_patient_id,
                    access_token=access_token,
                    fhir_base_url=fhir_base_url,
                )

                frame = to_dashboard_frame(
                    observation_bundle,
                    provider=provider_label(provider),
                    include_debug=debug,
                    medication_resources=medication_resources,
                )
                
                oracle_values = frame.get("debug", {}).get("rawExtractedFhirValues") or {
                "vitals": frame.get("vitals"),
                "labs": frame.get("labs"),
            }

                oracle_hash = hashlib.sha256(
                    json.dumps(oracle_values, sort_keys=True).encode("utf-8")
                ).hexdigest()[:10]

                oracle_changed = oracle_hash != last_oracle_hash
                last_oracle_hash = oracle_hash

                quality = frame.get("dataQuality", {})

                print(
                    "[KGEN ORACLE SSE]",
                    f"provider={provider_label(provider)}",
                    f"patient={effective_patient_id}",
                    f"receivedAt={frame.get('receivedAt')}",
                    f"fhirFields={quality.get('fhirFields')}",
                    f"fallbackFields={quality.get('fallbackFields')}",
                    f"observationCount={quality.get('observationCount')}",
                    f"matchedObservationCount={quality.get('matchedObservationCount')}",
                    f"oracleHash={oracle_hash}",
                    f"oracleChanged={oracle_changed}",
                )
                payload = json.dumps(frame, separators=(",", ":"))

                if payload != last_payload:
                    last_payload = payload

                    yield "event: fhir-frame\n"
                    yield f"data: {payload}\n\n"

                    yield "event: firely-frame\n"
                    yield f"data: {payload}\n\n"
                else:
                    heartbeat = {
                        "status": "heartbeat",
                        "provider": provider,
                        "receivedAt": now_iso(),
                    }
                    yield "event: heartbeat\n"
                    yield f"data: {json.dumps(heartbeat)}\n\n"

            except Exception as error:
                error_frame = build_error_frame(provider, error)
                payload = json.dumps(error_frame, separators=(",", ":"))

                yield "event: fhir-frame\n"
                yield f"data: {payload}\n\n"

                yield "event: firely-frame\n"
                yield f"data: {payload}\n\n"

            await asyncio.sleep(settings.POLL_SECONDS)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def resolve_patient_id(
    *,
    provider: str,
    requested_patient_id: str | None,
    token_state: dict[str, Any] | None,
) -> str | None:
    if requested_patient_id:
        return requested_patient_id

    if provider == "oracle":
        if token_state and token_state.get("patient_id"):
            return token_state["patient_id"]

        # Allow a known sandbox patient id even in smart mode.
        if settings.ORACLE_TEST_PATIENT_ID:
            return settings.ORACLE_TEST_PATIENT_ID

    return None



def provider_label(provider: str) -> str:
    if provider == "firely":
        return "firely-public-sandbox"

    if provider == "oracle":
        return f"oracle-{settings.ORACLE_MODE}"

    return provider


def build_error_frame(provider: str, error: Exception) -> dict[str, Any]:
    return {
        "source": provider,
        "status": "error",
        "timestamp": now_iso(),
        "receivedAt": now_iso(),
        "overallColor": "yellow",
        "error": str(error),
        "vitals": {},
        "labs": {},
        "colors": {},
        "fallbackUsed": [],
        "dataQuality": {
            "fhirFieldCount": 0,
            "firelyFieldCount": 0,
            "fallbackFieldCount": 0,
            "fhirFields": [],
            "firelyFields": [],
            "fallbackFields": [],
            "missingRawFhirFields": list(FIELD_LABELS.keys()),
            "missingRawFirelyFields": list(FIELD_LABELS.keys()),
            "observationCount": 0,
            "matchedObservationCount": 0,
        },
        "interpretation": {
            "title": "FHIR stream warning",
            "rhythm": "The backend could not fetch the latest FHIR Observations.",
            "ppg": "The dashboard can continue showing local waveform simulation.",
            "likelyEtiology": "Check backend logs, provider configuration, SMART token state, network access, or patient_id filtering.",
        },
        "priorityTrends": [],
        "medicationRows": [],
        "contextAlerts": [],
    }
    
@app.get("/api/fhir/oracle/session")
async def oracle_session_debug(request: Request):
    token_state = get_token_for_request(request)

    if not token_state:
        return {
            "hasOracleSession": False,
            "message": "No Oracle SMART session cookie found. Complete /auth/oracle/launch in the same browser."
        }

    return {
        "hasOracleSession": True,
        "provider": token_state.get("provider"),
        "fhirBaseUrl": token_state.get("fhir_base_url"),
        "hasAccessToken": bool(token_state.get("access_token")),
        "hasRefreshToken": bool(token_state.get("refresh_token")),
        "patientIdFromToken": token_state.get("patient_id"),
        "encounterIdFromToken": token_state.get("encounter_id"),
        "scope": token_state.get("scope"),
        "expiresAtEpoch": token_state.get("expires_at_epoch"),
    }
    

@app.get("/api/fhir/oracle/raw/observations")
async def raw_oracle_observations(
    request: Request,
    patient_id: str | None = Query(default=None),
):
    token_state = get_token_for_request(request)

    effective_patient_id = resolve_patient_id(
        provider="oracle",
        requested_patient_id=patient_id,
        token_state=token_state,
    )

    bundle = await fetch_provider_observations(
        "oracle",
        effective_patient_id,
        access_token=token_state.get("access_token") if token_state else None,
        fhir_base_url=token_state.get("fhir_base_url") if token_state else None,
    )

    return {
        "provider": "oracle",
        "effectivePatientId": effective_patient_id,
        "bundleType": bundle.get("type"),
        "bundleTotal": bundle.get("total"),
        "entryCount": len(bundle.get("entry", []) or []),
        "rawBundle": bundle,
    }