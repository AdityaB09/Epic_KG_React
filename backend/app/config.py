import os
from dotenv import load_dotenv

load_dotenv()


def csv_env(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


class Settings:
    # Generic
    FHIR_PROVIDER = os.getenv("FHIR_PROVIDER", "epic").lower()
    POLL_SECONDS = float(os.getenv("POLL_SECONDS", "10"))
    USE_FALLBACK_DEMO_DATA = os.getenv("USE_FALLBACK_DEMO_DATA", "true").lower() == "true"
    DEMO_PATIENT_ID = os.getenv("DEMO_PATIENT_ID", "kardiogenics-demo")
    DEBUG_FHIR_LOGS = os.getenv(
        "DEBUG_FHIR_LOGS",
        os.getenv("DEBUG_FIRELY_LOGS", "true"),
    ).lower() == "true"
    MAX_DEBUG_OBSERVATIONS = int(os.getenv("MAX_DEBUG_OBSERVATIONS", "25"))

    # Firely sandbox. Keep this working.
    FIRELY_BASE_URL = os.getenv("FIRELY_BASE_URL", "https://server.fire.ly").rstrip("/")

    # Epic FHIR sandbox / SMART on FHIR
    EPIC_MODE = os.getenv("EPIC_MODE", "smart").lower()
    EPIC_FHIR_BASE_URL = os.getenv(
        "EPIC_FHIR_BASE_URL",
        "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
    ).rstrip("/")
    EPIC_CLIENT_ID = os.getenv("EPIC_CLIENT_ID", "")
    EPIC_REDIRECT_URI = os.getenv(
        "EPIC_REDIRECT_URI",
        "http://127.0.0.1:8000/auth/epic/callback",
    )
    EPIC_LAUNCH_URI = os.getenv(
        "EPIC_LAUNCH_URI",
        "http://127.0.0.1:8000/auth/epic/launch",
    )

    # EHR launch should include launch.
    EPIC_EHR_SCOPES = os.getenv(
        "EPIC_EHR_SCOPES",
        "launch openid fhirUser",
    )

    # Standalone launch should not include launch.
    EPIC_STANDALONE_SCOPES = os.getenv(
        "EPIC_STANDALONE_SCOPES",
        "openid fhirUser",
    )

    # Use only for sandbox testing when EHR launch does not return patient context.
    EPIC_TEST_PATIENT_ID = os.getenv("EPIC_TEST_PATIENT_ID", "")

    # Security allowlist for accepted Epic iss values.
    # If empty, the configured EPIC_FHIR_BASE_URL is allowed.
    EPIC_ALLOWED_ISSUERS = csv_env("EPIC_ALLOWED_ISSUERS")

    EPIC_FRONTEND_REDIRECT_URL = os.getenv(
        "EPIC_FRONTEND_REDIRECT_URL",
        "http://127.0.0.1:5173",
    )

    # Local dev signing only. Use a long random value.
    SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "dev-only-change-me")


settings = Settings()