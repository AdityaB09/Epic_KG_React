from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings
from app.fhir_http import fhir_get, bundle_resources


async def fetch_firely_observations(patient_id: str | None = None) -> dict[str, Any]:
    params = {
        "_sort": "-_lastUpdated",
        "_count": "200",
    }

    if patient_id:
        params["subject"] = f"Patient/{patient_id}"

    if settings.DEBUG_FHIR_LOGS:
        print("\n[FHIR REQUEST] provider=firely resource=Observation")
        print("BASE:", settings.FIRELY_BASE_URL)
        print("PARAMS:", params)

    bundle = await fhir_get(
        settings.FIRELY_BASE_URL,
        "/Observation",
        params=params,
    )

    if settings.DEBUG_FHIR_LOGS:
        print("[FHIR RESPONSE] provider=firely Observation")
        print("BUNDLE TOTAL:", bundle.get("total"))
        print("ENTRY COUNT:", len(bundle.get("entry", []) or []))

    return bundle


async def fetch_firely_patient_resources(
    resource_type: str,
    patient_id: str | None,
    *,
    count: int = 50,
) -> list[dict[str, Any]]:
    if not patient_id:
        return []

    try:
        bundle = await fhir_get(
            settings.FIRELY_BASE_URL,
            f"/{resource_type}",
            params={
                "patient": patient_id,
                "_count": str(count),
            },
        )
        return bundle_resources(bundle, resource_type)
    except Exception:
        return []


def empty_bundle(message: str) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 0,
        "entry": [],
        "issue": [
            {
                "severity": "information",
                "code": "informational",
                "diagnostics": message,
            }
        ],
    }


async def fetch_epic_observations(
    patient_id: str | None = None,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
) -> dict[str, Any]:
    base_url = (fhir_base_url or settings.EPIC_FHIR_BASE_URL).rstrip("/")

    if not base_url:
        raise HTTPException(
            status_code=500,
            detail="EPIC_FHIR_BASE_URL is not configured.",
        )

    if not patient_id:
        return empty_bundle(
            "No Epic patient_id is available. The backend skipped Epic Observation search. "
            "Use Epic EHR launch patient context or set EPIC_TEST_PATIENT_ID for sandbox testing."
        )

    search_attempts = [
        {
            "_count": "200",
            "_sort": "-date",
            "patient": patient_id,
        },
        {
            "_count": "200",
            "patient": patient_id,
        },
        {
            "_count": "200",
            "subject": f"Patient/{patient_id}",
        },
    ]

    last_error: Exception | None = None

    for params in search_attempts:
        if settings.DEBUG_FHIR_LOGS:
            print("\n[FHIR REQUEST] provider=epic resource=Observation")
            print("BASE:", base_url)
            print("PARAMS:", params)
            print("TOKEN:", "present" if access_token else "missing")

        try:
            return await fhir_get(
                base_url,
                "/Observation",
                params=params,
                access_token=access_token,
            )
        except httpx.HTTPStatusError as error:
            last_error = error

            if error.response.status_code in {400, 404}:
                continue

            raise

    return empty_bundle(
        "Epic Observation search failed for all patient search attempts. "
        f"Last error: {str(last_error)}"
    )




async def fetch_epic_patient_resources(
    resource_type: str,
    patient_id: str | None,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
    count: int = 50,
) -> list[dict[str, Any]]:
    base_url = (fhir_base_url or settings.EPIC_FHIR_BASE_URL).rstrip("/")

    if not base_url or not patient_id:
        return []

    attempts = [
        {
            "patient": patient_id,
            "_count": str(count),
        },
        {
            "subject": f"Patient/{patient_id}",
            "_count": str(count),
        },
    ]

    for params in attempts:
        try:
            bundle = await fhir_get(
                base_url,
                f"/{resource_type}",
                params=params,
                access_token=access_token,
            )
            return bundle_resources(bundle, resource_type)
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {400, 404}:
                continue
            return []
        except Exception:
            return []

    return []


async def fetch_provider_observations(
    provider: str,
    patient_id: str | None,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
) -> dict[str, Any]:
    provider = provider.lower()

    if provider == "firely":
        return await fetch_firely_observations(patient_id)

    if provider == "epic":
        return await fetch_epic_observations(
            patient_id,
            access_token=access_token,
            fhir_base_url=fhir_base_url,
        )

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported FHIR provider: {provider}",
    )


async def fetch_provider_medications(
    provider: str,
    patient_id: str | None,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
) -> list[dict[str, Any]]:
    provider = provider.lower()

    if not patient_id:
        return []

    resources: list[dict[str, Any]] = []

    if provider == "firely":
        for resource_type in [
            "MedicationRequest",
            "MedicationAdministration",
            "MedicationDispense",
            "MedicationStatement",
        ]:
            resources.extend(
                await fetch_firely_patient_resources(
                    resource_type,
                    patient_id,
                    count=25,
                )
            )

        return resources

    if provider == "epic":
        for resource_type in [
            "MedicationRequest",
            "MedicationStatement",
            "MedicationAdministration",
            "MedicationDispense",
        ]:
            resources.extend(
                await fetch_epic_patient_resources(
                    resource_type,
                    patient_id,
                    access_token=access_token,
                    fhir_base_url=fhir_base_url,
                    count=25,
                )
            )

        return resources

    return []


async def test_provider_status(
    provider: str,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
) -> dict[str, Any]:
    provider = provider.lower()

    if provider == "firely":
        metadata = await fhir_get(settings.FIRELY_BASE_URL, "/metadata")
        return {
            "provider": "firely",
            "ok": True,
            "baseUrl": settings.FIRELY_BASE_URL,
            "software": metadata.get("software", {}).get("name"),
            "fhirVersion": metadata.get("fhirVersion"),
        }

    if provider == "epic":
        base_url = (fhir_base_url or settings.EPIC_FHIR_BASE_URL).rstrip("/")

        if not base_url:
            return {
                "provider": "epic",
                "ok": False,
                "error": "EPIC_FHIR_BASE_URL is missing.",
            }

        result = {
            "provider": "epic",
            "ok": True,
            "mode": settings.EPIC_MODE,
            "baseUrl": base_url,
            "clientIdConfigured": bool(settings.EPIC_CLIENT_ID),
        }

        try:
            smart_config = await fhir_get(
                base_url,
                "/.well-known/smart-configuration",
                access_token=access_token,
                extra_headers={"Epic-Client-ID": settings.EPIC_CLIENT_ID}
                if settings.EPIC_CLIENT_ID
                else None,
            )
            result["smartConfigurationAvailable"] = True
            result["authorizationEndpoint"] = smart_config.get("authorization_endpoint")
            result["tokenEndpoint"] = smart_config.get("token_endpoint")
            result["scopesSupported"] = smart_config.get("scopes_supported", [])
            result["codeChallengeMethodsSupported"] = smart_config.get(
                "code_challenge_methods_supported",
                [],
            )
        except Exception as error:
            result["smartConfigurationAvailable"] = False
            result["smartConfigurationError"] = str(error)

        try:
            metadata = await fhir_get(
                base_url,
                "/metadata",
                access_token=access_token,
                extra_headers={"Epic-Client-ID": settings.EPIC_CLIENT_ID}
                if settings.EPIC_CLIENT_ID
                else None,
            )
            result["metadataAvailable"] = True
            result["fhirVersion"] = metadata.get("fhirVersion")
        except Exception as error:
            result["metadataAvailable"] = False
            result["metadataError"] = str(error)

        return result

    return {
        "provider": provider,
        "ok": False,
        "error": "Unsupported provider.",
    }