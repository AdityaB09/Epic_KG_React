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


async def fetch_oracle_observations(
    patient_id: str | None = None,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
) -> dict[str, Any]:
    base_url = (fhir_base_url or settings.ORACLE_FHIR_BASE_URL).rstrip("/")

    if not base_url:
        raise HTTPException(
            status_code=500,
            detail="ORACLE_FHIR_BASE_URL is not configured.",
        )

    # IMPORTANT:
    # In standalone SMART login with user/... scopes, Oracle may not give patient context.
    # Do not call /Observation?_count=200 without patient context because Oracle rejects it.
    if not patient_id:
        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 0,
            "entry": [],
            "issue": [
                {
                    "severity": "information",
                    "code": "informational",
                    "diagnostics": (
                        "No Oracle patient_id is available. "
                        "The backend skipped Oracle Observation search to avoid a 400 response. "
                        "Use EHR launch patient context or provide a known Oracle sandbox patient id."
                    ),
                }
            ],
        }

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
            print("\n[FHIR REQUEST] provider=oracle resource=Observation")
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

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 0,
        "entry": [],
        "issue": [
            {
                "severity": "warning",
                "code": "processing",
                "diagnostics": (
                    "Oracle Observation search failed for all patient search attempts. "
                    f"Last error: {str(last_error)}"
                ),
            }
        ],
    }


async def fetch_oracle_patient_resources(
    resource_type: str,
    patient_id: str,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
    count: int = 50,
) -> list[dict[str, Any]]:
    base_url = (fhir_base_url or settings.ORACLE_FHIR_BASE_URL).rstrip("/")

    if not base_url:
        return []

    if not patient_id:
        return []

    params = {
        "patient": patient_id,
        "_count": str(count),
    }

    try:
        bundle = await fhir_get(
            base_url,
            f"/{resource_type}",
            params=params,
            access_token=access_token,
        )
        return bundle_resources(bundle, resource_type)

    except httpx.HTTPStatusError as error:
        # Retry with subject reference for resources that prefer subject.
        if error.response.status_code in {400, 404}:
            try:
                bundle = await fhir_get(
                    base_url,
                    f"/{resource_type}",
                    params={
                        "subject": f"Patient/{patient_id}",
                        "_count": str(count),
                    },
                    access_token=access_token,
                )
                return bundle_resources(bundle, resource_type)
            except Exception:
                return []

        return []

    except Exception:
        return []


async def fetch_provider_observations(
    provider: str,
    patient_id: str | None,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
) -> dict[str, Any]:
    return await fetch_oracle_observations(
        patient_id,
        access_token=access_token,
        fhir_base_url=fhir_base_url,
    )




async def fetch_provider_medications(
    provider: str,
    patient_id: str | None,
    *,
    access_token: str | None = None,
    fhir_base_url: str | None = None,
) -> list[dict[str, Any]]:
    if not patient_id:
        return []

    resources: list[dict[str, Any]] = []

    for resource_type in [
        "MedicationRequest",
        "MedicationAdministration",
        "MedicationDispense",
    ]:
        resources.extend(
            await fetch_oracle_patient_resources(
                resource_type,
                patient_id,
                access_token=access_token,
                fhir_base_url=fhir_base_url,
                count=25,
            )
        )

    return resources

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

    if provider == "oracle":
        base_url = (fhir_base_url or settings.ORACLE_FHIR_BASE_URL).rstrip("/")
        if not base_url:
            return {
                "provider": "oracle",
                "ok": False,
                "error": "ORACLE_FHIR_BASE_URL is missing.",
            }

        result = {
            "provider": "oracle",
            "ok": True,
            "mode": settings.ORACLE_MODE,
            "baseUrl": base_url,
            "clientIdConfigured": bool(settings.ORACLE_CLIENT_ID),
        }

        try:
            smart_config = await fhir_get(
                base_url,
                "/.well-known/smart-configuration",
                access_token=access_token,
            )
            result["smartConfigurationAvailable"] = True
            result["authorizationEndpoint"] = smart_config.get("authorization_endpoint")
            result["tokenEndpoint"] = smart_config.get("token_endpoint")
            result["scopesSupported"] = smart_config.get("scopes_supported", [])
            result["codeChallengeMethodsSupported"] = smart_config.get("code_challenge_methods_supported", [])
        except Exception as error:
            result["smartConfigurationAvailable"] = False
            result["smartConfigurationError"] = str(error)

        try:
            metadata = await fhir_get(
                base_url,
                "/metadata",
                access_token=access_token,
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