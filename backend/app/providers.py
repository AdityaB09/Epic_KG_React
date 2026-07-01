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

    # Epic often rejects very broad Observation searches.
    # Search category-specific Observations instead of:
    # Observation?_count=200&subject=Patient/{id}
    vital_loinc_codes = ",".join(
        [
            "http://loinc.org|8867-4",   # Heart rate
            "http://loinc.org|9279-1",   # Respiratory rate
            "http://loinc.org|59408-5",  # Oxygen saturation
            "http://loinc.org|8480-6",   # Systolic BP
            "http://loinc.org|8462-4",   # Diastolic BP
            "http://loinc.org|8310-5",   # Body temperature
        ]
    )

    lab_loinc_codes = ",".join(
        [
            "http://loinc.org|2339-0",   # Glucose
            "http://loinc.org|2345-7",   # Glucose
            "http://loinc.org|2823-3",   # Potassium
            "http://loinc.org|2160-0",   # Creatinine
            "http://loinc.org|6690-2",   # WBC / Leukocytes
        ]
    )

    search_attempts = [
        (
            "vital-signs category",
            {
                "patient": patient_id,
                "category": "vital-signs",
            },
        ),
        (
            "laboratory category",
            {
                "patient": patient_id,
                "category": "laboratory",
            },
        ),
        (
            "vital signs LOINC codes",
            {
                "patient": patient_id,
                "code": vital_loinc_codes,
            },
        ),
        (
            "lab LOINC codes",
            {
                "patient": patient_id,
                "code": lab_loinc_codes,
            },
        ),
    ]

    combined_entries: list[dict[str, Any]] = []
    seen_resource_keys: set[tuple[str | None, str | None]] = set()
    search_debug: list[dict[str, Any]] = []

    for label, params in search_attempts:
        if settings.DEBUG_FHIR_LOGS:
            print("\n[FHIR REQUEST] provider=epic resource=Observation")
            print("SEARCH LABEL:", label)
            print("BASE:", base_url)
            print("PARAMS:", params)
            print("TOKEN:", "present" if access_token else "missing")

        try:
            bundle = await fhir_get(
                base_url,
                "/Observation",
                params=params,
                access_token=access_token,
            )

            entries = bundle.get("entry", []) or []

            search_debug.append(
                {
                    "label": label,
                    "ok": True,
                    "bundleTotal": bundle.get("total"),
                    "entryCount": len(entries),
                    "params": params,
                }
            )

            for entry in entries:
                resource = entry.get("resource", {}) if isinstance(entry, dict) else {}
                resource_key = (
                    resource.get("resourceType"),
                    resource.get("id"),
                )

                if resource_key in seen_resource_keys:
                    continue

                seen_resource_keys.add(resource_key)
                combined_entries.append(entry)

        except httpx.HTTPStatusError as error:
            error_text = ""
            try:
                error_text = error.response.text[:800]
            except Exception:
                error_text = str(error)

            search_debug.append(
                {
                    "label": label,
                    "ok": False,
                    "statusCode": error.response.status_code,
                    "params": params,
                    "error": error_text,
                }
            )

            if settings.DEBUG_FHIR_LOGS:
                print("[FHIR ERROR] provider=epic resource=Observation")
                print("SEARCH LABEL:", label)
                print("STATUS:", error.response.status_code)
                print("BODY:", error_text)

            # Continue trying the next Epic-supported search shape.
            continue

    combined_bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(combined_entries),
        "entry": combined_entries,
        "searchDebug": search_debug,
    }

    if not combined_entries:
        combined_bundle["issue"] = [
            {
                "severity": "information",
                "code": "informational",
                "diagnostics": (
                    "Epic SMART session is valid, but Epic returned zero Observation entries "
                    "for this selected patient using category/code searches. Try another LaunchPad patient, "
                    "or inspect searchDebug for the exact Epic response."
                ),
            }
        ]

    return combined_bundle


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