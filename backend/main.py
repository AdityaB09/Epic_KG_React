import asyncio
import copy
import hashlib
import json
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.epic_smart import get_token_for_request, router as epic_smart_router
from app.normalizer import FIELD_LABELS, now_iso, to_dashboard_frame
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

app.include_router(epic_smart_router)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "provider": settings.FHIR_PROVIDER,
        "pollSeconds": settings.POLL_SECONDS,
        "fallbackDemoData": settings.USE_FALLBACK_DEMO_DATA,
        "firelyBaseUrl": settings.FIRELY_BASE_URL,
        "epicMode": settings.EPIC_MODE,
        "epicBaseUrlConfigured": bool(settings.EPIC_FHIR_BASE_URL),
        "epicClientIdConfigured": bool(settings.EPIC_CLIENT_ID),
    }


@app.get("/api/fhir/status")
async def fhir_status(
    provider: str = Query(default=settings.FHIR_PROVIDER),
):
    return await test_provider_status(provider)


@app.get("/api/fhir/epic/status")
async def epic_status(request: Request):
    token_state = get_token_for_request(request)

    return await test_provider_status(
        "epic",
        access_token=token_state.get("access_token") if token_state else None,
        fhir_base_url=token_state.get("fhir_base_url") if token_state else None,
    )


@app.get("/api/fhir/epic/session")
async def epic_session_debug(request: Request):
    token_state = get_token_for_request(request)

    if not token_state:
        return {
            "hasEpicSession": False,
            "message": "No Epic SMART session cookie found. Complete /auth/epic/launch or /auth/epic/standalone in this browser.",
        }

    return {
        "hasEpicSession": True,
        "provider": token_state.get("provider"),
        "fhirBaseUrl": token_state.get("fhir_base_url"),
        "hasAccessToken": bool(token_state.get("access_token")),
        "hasRefreshToken": bool(token_state.get("refresh_token")),
        "patientIdFromToken": token_state.get("patient_id"),
        "encounterIdFromToken": token_state.get("encounter_id"),
        "locationIdFromToken": token_state.get("location_id"),
        "scope": token_state.get("scope"),
        "expiresAtEpoch": token_state.get("expires_at_epoch"),
    }


@app.get("/api/fhir/latest")
async def latest_fhir_frame(
    request: Request,
    provider: str = Query(default=settings.FHIR_PROVIDER),
    patient_id: str | None = Query(default=None),
    debug: bool = Query(default=False),
):
    provider = provider.lower()
    token_state = get_token_for_request(request) if provider == "epic" else None

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


@app.get("/api/firely/raw")
async def raw_firely_observations(
    patient_id: str | None = Query(default=None),
):
    return await fetch_provider_observations("firely", patient_id)


@app.get("/api/firely/latest")
async def latest_firely_frame(
    patient_id: str | None = Query(default=None),
    debug: bool = Query(default=False),
):
    observation_bundle = await fetch_provider_observations("firely", patient_id)
    medication_resources = await fetch_provider_medications("firely", patient_id)

    return to_dashboard_frame(
        observation_bundle,
        provider=provider_label("firely"),
        include_debug=debug,
        medication_resources=medication_resources,
    )


@app.get("/api/firely/debug/latest")
async def latest_firely_debug_frame(
    patient_id: str | None = Query(default=None),
):
    observation_bundle = await fetch_provider_observations("firely", patient_id)
    medication_resources = await fetch_provider_medications("firely", patient_id)

    return to_dashboard_frame(
        observation_bundle,
        provider=provider_label("firely"),
        include_debug=True,
        medication_resources=medication_resources,
    )


@app.get("/api/firely/stream")
async def stream_firely_frame(
    request: Request,
    patient_id: str | None = Query(default=None),
    debug: bool = Query(default=False),
):
    return make_streaming_response(
        request=request,
        provider="firely",
        patient_id=patient_id,
        debug=debug,
    )


@app.get("/api/stream")
async def stream_fhir_frame(
    request: Request,
    provider: str = Query(default=settings.FHIR_PROVIDER),
    patient_id: str | None = Query(default=None),
    debug: bool = Query(default=False),
):
    return make_streaming_response(
        request=request,
        provider=provider.lower(),
        patient_id=patient_id,
        debug=debug,
    )


@app.get("/api/fhir/epic/raw/observations")
async def raw_epic_observations(
    request: Request,
    patient_id: str | None = Query(default=None),
):
    token_state = get_token_for_request(request)

    effective_patient_id = resolve_patient_id(
        provider="epic",
        requested_patient_id=patient_id,
        token_state=token_state,
    )

    bundle = await fetch_provider_observations(
        "epic",
        effective_patient_id,
        access_token=token_state.get("access_token") if token_state else None,
        fhir_base_url=token_state.get("fhir_base_url") if token_state else None,
    )

    return {
        "provider": "epic",
        "effectivePatientId": effective_patient_id,
        "bundleType": bundle.get("type"),
        "bundleTotal": bundle.get("total"),
        "entryCount": len(bundle.get("entry", []) or []),
        "rawBundle": bundle,
    }


def make_streaming_response(
    *,
    request: Request,
    provider: str,
    patient_id: str | None,
    debug: bool,
):
    async def event_generator():
        last_content_hash = None

        while True:
            try:
                token_state = get_token_for_request(request) if provider == "epic" else None

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

                frame_with_debug = to_dashboard_frame(
                    observation_bundle,
                    provider=provider_label(provider),
                    include_debug=True,
                    medication_resources=medication_resources,
                )

                content_hash = build_content_hash(frame_with_debug)
                changed = content_hash != last_content_hash

                quality = frame_with_debug.get("dataQuality", {})

                if settings.DEBUG_FHIR_LOGS:
                    print(
                        "[KGEN FHIR SSE]",
                        f"provider={provider_label(provider)}",
                        f"patient={effective_patient_id}",
                        f"receivedAt={frame_with_debug.get('receivedAt')}",
                        f"fhirFields={quality.get('fhirFields')}",
                        f"fallbackFields={quality.get('fallbackFields')}",
                        f"observationCount={quality.get('observationCount')}",
                        f"matchedObservationCount={quality.get('matchedObservationCount')}",
                        f"contentHash={content_hash}",
                        f"changed={changed}",
                    )

                if changed:
                    last_content_hash = content_hash
                    frame_to_send = frame_with_debug if debug else without_debug(frame_with_debug)
                    payload = json.dumps(frame_to_send, separators=(",", ":"))

                    yield "event: fhir-frame\n"
                    yield f"data: {payload}\n\n"
                else:
                    heartbeat = {
                        "status": "heartbeat",
                        "provider": provider_label(provider),
                        "patientId": effective_patient_id,
                        "contentHash": content_hash,
                        "receivedAt": now_iso(),
                    }
                    yield "event: heartbeat\n"
                    yield f"data: {json.dumps(heartbeat, separators=(',', ':'))}\n\n"

            except Exception as error:
                error_frame = build_error_frame(provider, error)
                payload = json.dumps(error_frame, separators=(",", ":"))

                yield "event: fhir-frame\n"
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


def build_content_hash(frame: dict[str, Any]) -> str:
    debug = frame.get("debug", {})
    hash_source = {
        "rawExtractedFhirValues": debug.get("rawExtractedFhirValues"),
        "fhirFields": frame.get("dataQuality", {}).get("fhirFields"),
        "fallbackFields": frame.get("dataQuality", {}).get("fallbackFields"),
        "medicationRows": frame.get("medicationRows"),
        "contextAlerts": frame.get("contextAlerts"),
    }

    return hashlib.sha256(
        json.dumps(hash_source, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]


def without_debug(frame: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(frame)
    clean.pop("debug", None)
    return clean


def resolve_patient_id(
    *,
    provider: str,
    requested_patient_id: str | None,
    token_state: dict[str, Any] | None,
) -> str | None:
    if requested_patient_id:
        return requested_patient_id

    if provider == "epic":
        if token_state and token_state.get("patient_id"):
            return token_state["patient_id"]

        if settings.EPIC_TEST_PATIENT_ID:
            return settings.EPIC_TEST_PATIENT_ID

    return None


def provider_label(provider: str) -> str:
    provider = provider.lower()

    if provider == "firely":
        return "firely-public-sandbox"

    if provider == "epic":
        return f"epic-{settings.EPIC_MODE}"

    return provider


def build_error_frame(provider: str, error: Exception) -> dict[str, Any]:
    return {
        "source": provider_label(provider),
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
            "fallbackFieldCount": 0,
            "fhirFields": [],
            "fallbackFields": [],
            "missingRawFhirFields": list(FIELD_LABELS.keys()),
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
    
@app.get("/api/fhir/epic/raw/encounter")
async def raw_epic_encounter(request: Request):
    token_state = get_token_for_request(request)

    if not token_state:
        return {
            "ok": False,
            "message": "No Epic SMART session cookie found.",
        }

    encounter_id = token_state.get("encounter_id")

    if not encounter_id:
        return {
            "ok": False,
            "message": "No encounter_id was returned in the Epic SMART launch token.",
            "session": {
                "patientIdFromToken": token_state.get("patient_id"),
                "encounterIdFromToken": token_state.get("encounter_id"),
            },
        }

    from app.fhir_http import fhir_get

    encounter = await fhir_get(
        token_state["fhir_base_url"],
        f"/Encounter/{encounter_id}",
        access_token=token_state.get("access_token"),
    )

    return {
        "ok": True,
        "provider": "epic",
        "encounterId": encounter_id,
        "encounter": encounter,
    }