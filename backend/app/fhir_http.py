from typing import Any

import httpx


FHIR_HEADERS = {
    "Accept": "application/fhir+json, application/json",
}


async def fhir_get(
    base_url: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    access_token: str | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    headers = dict(FHIR_HEADERS)

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    if extra_headers:
        headers.update(extra_headers)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/{path.lstrip('/')}",
            params=params or {},
            headers=headers,
        )

    response.raise_for_status()
    return response.json()


async def fhir_post_form(
    url: str,
    *,
    data: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    if headers:
        request_headers.update(headers)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            url,
            data=data,
            headers=request_headers,
        )

    response.raise_for_status()
    return response.json()


def bundle_resources(
    bundle: dict[str, Any],
    resource_type: str | None = None,
) -> list[dict[str, Any]]:
    resources = [
        entry.get("resource")
        for entry in bundle.get("entry", []) or []
        if isinstance(entry.get("resource"), dict)
    ]

    if resource_type:
        resources = [
            resource
            for resource in resources
            if resource.get("resourceType") == resource_type
        ]

    return resources