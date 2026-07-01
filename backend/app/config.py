import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Generic
    FHIR_PROVIDER = os.getenv("FHIR_PROVIDER", "firely").lower()
    POLL_SECONDS = float(os.getenv("POLL_SECONDS", "3"))
    USE_FALLBACK_DEMO_DATA = os.getenv("USE_FALLBACK_DEMO_DATA", "true").lower() == "true"
    DEMO_PATIENT_ID = os.getenv("DEMO_PATIENT_ID", "kardiogenics-demo")
    DEBUG_FHIR_LOGS = os.getenv(
        "DEBUG_FHIR_LOGS",
        os.getenv("DEBUG_FIRELY_LOGS", "true"),
    ).lower() == "true"
    MAX_DEBUG_OBSERVATIONS = int(os.getenv("MAX_DEBUG_OBSERVATIONS", "25"))

    # Firely
    FIRELY_BASE_URL = os.getenv("FIRELY_BASE_URL", "https://server.fire.ly").rstrip("/")

    # Oracle / Cerner
    ORACLE_MODE = os.getenv("ORACLE_MODE", "open").lower()  # open | smart
    ORACLE_FHIR_BASE_URL = os.getenv("ORACLE_FHIR_BASE_URL", "").rstrip("/")
    ORACLE_CLIENT_ID = os.getenv("ORACLE_CLIENT_ID", "")
    ORACLE_REDIRECT_URI = os.getenv(
        "ORACLE_REDIRECT_URI",
        "http://127.0.0.1:8000/auth/oracle/callback",
    )
    ORACLE_LAUNCH_URI = os.getenv(
        "ORACLE_LAUNCH_URI",
        "http://127.0.0.1:8000/auth/oracle/launch",
    )
    ORACLE_SCOPES = os.getenv(
        "ORACLE_SCOPES",
        (
            "launch openid fhirUser online_access "
            "patient/Patient.rs "
            "patient/Observation.rs "
            "patient/MedicationRequest.rs "
            "patient/MedicationAdministration.rs "
            "patient/MedicationDispense.rs "
            "patient/DiagnosticReport.rs "
            "patient/DocumentReference.rs "
            "patient/Encounter.rs "
            "patient/Condition.rs"
        ),
    )
    ORACLE_TEST_PATIENT_ID = os.getenv("ORACLE_TEST_PATIENT_ID", "")

    # Local demo session signing only. Not production.
    SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "dev-only-change-me")


settings = Settings()