import math
import random
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.fhir_http import bundle_resources


LOINC = {
    "heartRate": ["8867-4"],
    "respiratoryRate": ["9279-1"],
    "spo2": ["2708-6", "59408-5"],
    "temperature": ["8310-5"],
    "systolic": ["8480-6"],
    "diastolic": ["8462-4"],
    "bloodPressurePanel": ["85354-9"],
    "glucose": ["2339-0", "15074-8", "2345-7"],
    "potassium": ["6298-4", "2823-3"],
    "creatinine": ["2160-0", "38483-4"],
    "wbc": ["6690-2", "26464-8"],
}


FIELD_LABELS = {
    "heartRate": "Heart Rate",
    "respiratoryRate": "Respiratory Rate",
    "spo2": "SpO2",
    "systolic": "Systolic BP",
    "diastolic": "Diastolic BP",
    "temperature": "Temperature",
    "glucose": "Glucose",
    "potassium": "Potassium",
    "creatinine": "Creatinine",
    "wbc": "WBC",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_seed() -> float:
    return datetime.now(timezone.utc).timestamp() / max(settings.POLL_SECONDS, 1)


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def round_if_present(value: float | None, decimals: int = 0) -> float | int | None:
    if value is None:
        return None

    if decimals == 0:
        return int(round(value))

    return round(value, decimals)


def clinically_plausible(
    field: str,
    value: float | int | None,
    unit: str | None = None,
) -> bool:
    if value is None:
        return False

    try:
        value = float(value)
    except (TypeError, ValueError):
        return False

    ranges = {
        "heartRate": (20, 250),
        "respiratoryRate": (4, 80),
        "spo2": (50, 100),
        "systolic": (50, 260),
        "diastolic": (30, 160),
        "temperature": (30, 45),
        "glucose": (20, 700),
        "potassium": (1.5, 9.0),
        "creatinine": (0.1, 20.0),
        "wbc": (0.1, 100.0),
    }

    low, high = ranges.get(field, (-999999, 999999))
    return low <= value <= high


def get_codes(codeable: dict[str, Any] | None) -> set[str]:
    if not codeable:
        return set()

    codes = set()

    for coding in codeable.get("coding", []) or []:
        code = coding.get("code")
        if code:
            codes.add(str(code))

    return codes


def has_any_code(resource_or_component: dict[str, Any], target_codes: list[str]) -> bool:
    codes = get_codes(resource_or_component.get("code"))
    return bool(codes.intersection(set(target_codes)))


def get_quantity_value(resource_or_component: dict[str, Any]) -> float | None:
    quantity = resource_or_component.get("valueQuantity")

    if not isinstance(quantity, dict):
        return None

    return safe_float(quantity.get("value"))


def get_quantity_unit(resource_or_component: dict[str, Any]) -> str | None:
    quantity = resource_or_component.get("valueQuantity")

    if not isinstance(quantity, dict):
        return None

    return quantity.get("unit") or quantity.get("code")


def get_code_display(resource: dict[str, Any]) -> str:
    code = resource.get("code", {}) or {}

    if code.get("text"):
        return str(code["text"])

    coding = code.get("coding", []) or []
    if coding:
        return coding[0].get("display") or coding[0].get("code") or "Unknown Observation"

    return "Unknown Observation"


def get_subject_reference(resource: dict[str, Any]) -> str | None:
    subject = resource.get("subject")

    if isinstance(subject, dict):
        return subject.get("reference")

    return None


def get_observation_timestamp(obs: dict[str, Any]) -> str | None:
    return (
        obs.get("effectiveDateTime")
        or obs.get("issued")
        or obs.get("meta", {}).get("lastUpdated")
    )


def get_component_quantity_with_source(
    obs: dict[str, Any],
    target_codes: list[str],
) -> tuple[float | None, str | None, str | None]:
    for component in obs.get("component", []) or []:
        if has_any_code(component, target_codes):
            value = get_quantity_value(component)
            unit = get_quantity_unit(component)
            codes = sorted(list(get_codes(component.get("code"))))
            code = codes[0] if codes else None

            if value is not None:
                return value, unit, code

    return None, None, None


def empty_dashboard_values() -> dict[str, Any]:
    return {
        "heartRate": None,
        "respiratoryRate": None,
        "spo2": None,
        "systolic": None,
        "diastolic": None,
        "temperature": None,
        "glucose": None,
        "potassium": None,
        "creatinine": None,
        "wbc": None,
    }


def observation_summary(obs: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": obs.get("id"),
        "resourceType": obs.get("resourceType"),
        "display": get_code_display(obs),
        "codes": sorted(list(get_codes(obs.get("code")))),
        "subject": get_subject_reference(obs),
        "timestamp": get_observation_timestamp(obs),
        "lastUpdated": obs.get("meta", {}).get("lastUpdated"),
        "value": get_quantity_value(obs),
        "unit": get_quantity_unit(obs),
        "componentCount": len(obs.get("component", []) or []),
        "matchedFields": [],
    }


def make_source_detail(
    *,
    field: str,
    obs: dict[str, Any],
    value: float | int,
    unit: str | None,
    provider: str,
    component_code: str | None = None,
) -> dict[str, Any]:
    return {
        "field": field,
        "source": provider,
        "observationId": obs.get("id"),
        "display": get_code_display(obs),
        "codes": sorted(list(get_codes(obs.get("code")))),
        "componentCode": component_code,
        "subject": get_subject_reference(obs),
        "timestamp": get_observation_timestamp(obs),
        "lastUpdated": obs.get("meta", {}).get("lastUpdated"),
        "rawValue": value,
        "unit": unit,
    }


def extract_dashboard_values(
    bundle: dict[str, Any],
    *,
    provider: str,
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any], dict[str, Any]]:
    values = empty_dashboard_values()
    timestamps: dict[str, str] = {}
    sources: dict[str, Any] = {}

    observations = bundle_resources(bundle, "Observation")

    scan_report = {
        "bundleType": bundle.get("type"),
        "bundleTotal": bundle.get("total"),
        "entryCount": len(bundle.get("entry", []) or []),
        "observationCount": len(observations),
        "matchedObservationCount": 0,
        "observationsScanned": [],
    }

    for obs in observations:
        timestamp = get_observation_timestamp(obs)
        summary = observation_summary(obs)

        direct_mappings = [
            ("heartRate", LOINC["heartRate"]),
            ("respiratoryRate", LOINC["respiratoryRate"]),
            ("spo2", LOINC["spo2"]),
            ("temperature", LOINC["temperature"]),
            ("glucose", LOINC["glucose"]),
            ("potassium", LOINC["potassium"]),
            ("creatinine", LOINC["creatinine"]),
            ("wbc", LOINC["wbc"]),
        ]

        for field, codes in direct_mappings:
            if values[field] is None and has_any_code(obs, codes):
                quantity_value = get_quantity_value(obs)
                unit = get_quantity_unit(obs)

                if quantity_value is not None and clinically_plausible(field, quantity_value, unit):
                    values[field] = quantity_value

                    if timestamp:
                        timestamps[field] = timestamp

                    sources[field] = make_source_detail(
                        field=field,
                        obs=obs,
                        value=quantity_value,
                        unit=unit,
                        provider=provider,
                    )

                    summary["matchedFields"].append(
                        {
                            "field": field,
                            "matchedCodes": codes,
                            "value": quantity_value,
                            "unit": unit,
                        }
                    )

        if values["systolic"] is None:
            systolic, systolic_unit, component_code = get_component_quantity_with_source(
                obs,
                LOINC["systolic"],
            )

            if systolic is not None and clinically_plausible("systolic", systolic, systolic_unit):
                values["systolic"] = systolic

                if timestamp:
                    timestamps["systolic"] = timestamp

                sources["systolic"] = make_source_detail(
                    field="systolic",
                    obs=obs,
                    value=systolic,
                    unit=systolic_unit,
                    provider=provider,
                    component_code=component_code,
                )

                summary["matchedFields"].append(
                    {
                        "field": "systolic",
                        "matchedCodes": LOINC["systolic"],
                        "value": systolic,
                        "unit": systolic_unit,
                        "componentCode": component_code,
                    }
                )

        if values["diastolic"] is None:
            diastolic, diastolic_unit, component_code = get_component_quantity_with_source(
                obs,
                LOINC["diastolic"],
            )

            if diastolic is not None and clinically_plausible("diastolic", diastolic, diastolic_unit):
                values["diastolic"] = diastolic

                if timestamp:
                    timestamps["diastolic"] = timestamp

                sources["diastolic"] = make_source_detail(
                    field="diastolic",
                    obs=obs,
                    value=diastolic,
                    unit=diastolic_unit,
                    provider=provider,
                    component_code=component_code,
                )

                summary["matchedFields"].append(
                    {
                        "field": "diastolic",
                        "matchedCodes": LOINC["diastolic"],
                        "value": diastolic,
                        "unit": diastolic_unit,
                        "componentCode": component_code,
                    }
                )

        if summary["matchedFields"]:
            scan_report["matchedObservationCount"] += 1

        if len(scan_report["observationsScanned"]) < settings.MAX_DEBUG_OBSERVATIONS:
            scan_report["observationsScanned"].append(summary)

    return values, timestamps, sources, scan_report


def fallback_demo_values() -> dict[str, Any]:
    t = now_seed()

    return {
        "heartRate": round(118 + math.sin(t / 2.0) * 30 + random.uniform(-5, 5)),
        "respiratoryRate": round(24 + math.sin(t / 3.0) * 8 + random.uniform(-2, 2)),
        "spo2": round(max(88, min(100, 96 + math.sin(t / 4.0) * 3 + random.uniform(-1, 1)))),
        "systolic": round(128 + math.sin(t / 5.0) * 10 + random.uniform(-3, 3)),
        "diastolic": round(82 + math.sin(t / 5.3) * 7 + random.uniform(-2, 2)),
        "temperature": round(37.1 + math.sin(t / 6.0) * 0.35 + random.uniform(-0.1, 0.1), 1),
        "glucose": round(190 + math.sin(t / 2.5) * 42 + random.uniform(-8, 8)),
        "potassium": round(5.15 + math.sin(t / 3.3) * 0.38 + random.uniform(-0.08, 0.08), 1),
        "creatinine": round(1.25 + math.sin(t / 4.2) * 0.25 + random.uniform(-0.04, 0.04), 2),
        "wbc": round(11.2 + math.sin(t / 3.7) * 1.2 + random.uniform(-0.2, 0.2), 1),
    }


def fill_missing_values(values: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if not settings.USE_FALLBACK_DEMO_DATA:
        return values, [key for key, value in values.items() if value is None]

    fallback = fallback_demo_values()
    fallback_used = []
    merged = {}

    for key, fallback_value in fallback.items():
        if values.get(key) is None:
            merged[key] = fallback_value
            fallback_used.append(key)
        else:
            merged[key] = values[key]

    return merged, fallback_used


def classify_field(field: str, value: float | int | None) -> str:
    if value is None:
        return "yellow"

    if field == "heartRate":
        if value >= 125 or value <= 45:
            return "red"
        if value >= 105 or value <= 55:
            return "yellow"
        return "blue"

    if field == "respiratoryRate":
        if value >= 30 or value <= 8:
            return "red"
        if value >= 24 or value <= 11:
            return "yellow"
        return "blue"

    if field == "spo2":
        if value <= 90:
            return "red"
        if value <= 94:
            return "yellow"
        return "blue"

    if field == "temperature":
        if value >= 38.5 or value <= 35.0:
            return "red"
        if value >= 37.8 or value <= 36.0:
            return "yellow"
        return "blue"

    if field == "glucose":
        if value >= 220 or value <= 55:
            return "red"
        if value >= 180 or value <= 70:
            return "yellow"
        return "blue"

    if field == "potassium":
        if value >= 5.5 or value <= 3.0:
            return "red"
        if value >= 5.1 or value <= 3.4:
            return "yellow"
        return "blue"

    if field == "creatinine":
        if value >= 1.45:
            return "red"
        if value >= 1.25:
            return "yellow"
        return "blue"

    if field == "wbc":
        if value >= 12.0 or value <= 3.0:
            return "red"
        if value >= 11.0 or value <= 4.0:
            return "yellow"
        return "blue"

    if field == "systolic":
        if value >= 180 or value <= 80:
            return "red"
        if value >= 140 or value <= 90:
            return "yellow"
        return "blue"

    if field == "diastolic":
        if value >= 120 or value <= 45:
            return "red"
        if value >= 90 or value <= 55:
            return "yellow"
        return "blue"

    return "blue"


def overall_color(colors: dict[str, str]) -> str:
    rank = {"blue": 0, "yellow": 1, "red": 2}
    worst = "blue"

    for color in colors.values():
        if rank.get(color, 0) > rank.get(worst, 0):
            worst = color

    return worst


def medication_name(resource: dict[str, Any]) -> str:
    med = (
        resource.get("medicationCodeableConcept")
        or resource.get("medication")
        or {}
    )

    if isinstance(med, dict):
        if med.get("text"):
            return str(med["text"])

        coding = med.get("coding") or []
        if isinstance(coding, list) and coding:
            display = coding[0].get("display") or coding[0].get("code")
            if display:
                return str(display)

    med_ref = resource.get("medicationReference") or {}

    if isinstance(med_ref, dict):
        if med_ref.get("display"):
            return str(med_ref["display"])

        if med_ref.get("reference"):
            return str(med_ref["reference"])

    code = resource.get("code") or {}

    if isinstance(code, dict):
        if code.get("text"):
            return str(code["text"])

        coding = code.get("coding") or []
        if isinstance(coding, list) and coding:
            display = coding[0].get("display") or coding[0].get("code")
            if display:
                return str(display)

    return resource.get("id") or resource.get("resourceType") or "Medication"


def dosage_text(resource: dict[str, Any]) -> str:
    """
    Oracle/Cerner medication resources do not always shape dosage the same way.

    MedicationRequest usually has:
      dosageInstruction: [ { text, timing, doseAndRate } ]

    MedicationAdministration can have:
      dosage: { text, dose, route, method }

    MedicationDispense may have:
      dosageInstruction: [ ... ]

    This function safely handles list, dict, string, or missing dosage.
    """
    instructions = (
        resource.get("dosageInstruction")
        or resource.get("dosage")
        or resource.get("dosageInstructionText")
        or []
    )

    if isinstance(instructions, list):
        if not instructions:
            return "Check dosage"

        first = instructions[0]

        if isinstance(first, dict):
            text = first.get("text")
            if text:
                return str(text)

            timing_text = (
                first.get("timing", {})
                .get("code", {})
                .get("text")
            )
            if timing_text:
                return str(timing_text)

            dose_and_rate = first.get("doseAndRate") or []
            if isinstance(dose_and_rate, list) and dose_and_rate:
                dose_quantity = dose_and_rate[0].get("doseQuantity", {})
                value = dose_quantity.get("value")
                unit = dose_quantity.get("unit") or dose_quantity.get("code")

                if value is not None:
                    return f"{value} {unit or ''}".strip()

            return "Check dosage"

        if isinstance(first, str):
            return first

        return "Check dosage"

    if isinstance(instructions, dict):
        text = instructions.get("text")
        if text:
            return str(text)

        dose = instructions.get("dose")

        if isinstance(dose, dict):
            value = dose.get("value")
            unit = dose.get("unit") or dose.get("code")

            if value is not None:
                return f"{value} {unit or ''}".strip()

        route = instructions.get("route", {})
        route_text = route.get("text") if isinstance(route, dict) else None

        if route_text:
            return str(route_text)

        return "Check dosage"

    if isinstance(instructions, str):
        return instructions

    return "Check dosage"


def normalize_medications(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    meds = []

    for index, resource in enumerate(resources):
        try:
            resource_type = resource.get("resourceType", "Medication")
            name = medication_name(resource)
            date = (
                resource.get("authoredOn")
                or resource.get("effectiveDateTime")
                or resource.get("whenHandedOver")
                or resource.get("whenPrepared")
                or resource.get("whenHandedOver")
                or resource.get("meta", {}).get("lastUpdated")
                or "FHIR record"
            )

            dose = dosage_text(resource)

            meds.append(
                {
                    "id": resource.get("id") or f"med-{index}",
                    "name": name,
                    "med": name,
                    "sub": resource.get("status") or resource_type,
                    "dose": dose,
                    "frequency": dose,
                    "prescribed": str(date)[:10],
                    "status": resource.get("status") or "available",
                    "sourceResource": resource_type,
                    "taken": [
                        {
                            "ok": resource.get("status") not in {
                                "stopped",
                                "cancelled",
                                "entered-in-error",
                            },
                            "time": str(date)[11:16] if len(str(date)) >= 16 else "--",
                            "source": resource_type,
                        }
                    ],
                    "date": str(date)[:10],
                }
            )

        except Exception as error:
            meds.append(
                {
                    "id": resource.get("id") or f"med-error-{index}",
                    "name": resource.get("resourceType", "Medication"),
                    "med": resource.get("resourceType", "Medication"),
                    "sub": "FHIR medication parse warning",
                    "dose": "Check dosage",
                    "frequency": "Check dosage",
                    "prescribed": "FHIR record",
                    "status": "parse-warning",
                    "sourceResource": resource.get("resourceType", "Medication"),
                    "taken": [
                        {
                            "ok": False,
                            "time": "--",
                            "source": f"parse error: {str(error)}",
                        }
                    ],
                    "date": "FHIR record",
                }
            )

    return meds


def build_context_alerts(
    values: dict[str, Any],
    colors: dict[str, str],
    medications: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alerts = []

    med_text = " ".join(
        f"{med.get('name', '')} {med.get('med', '')}".lower()
        for med in medications
    )

    potassium = values.get("potassium")
    creatinine = values.get("creatinine")
    spo2 = values.get("spo2")
    rr = values.get("respiratoryRate")
    wbc = values.get("wbc")
    temp = values.get("temperature")
    glucose = values.get("glucose")
    heart_rate = values.get("heartRate")

    beta_blockers = [
        "metoprolol",
        "atenolol",
        "carvedilol",
        "propranolol",
        "bisoprolol",
        "labetalol",
    ]

    glucose_lowering = [
        "insulin",
        "glipizide",
        "glyburide",
        "glimepiride",
        "metformin",
        "semaglutide",
        "liraglutide",
    ]

    if heart_rate is not None and heart_rate <= 55:
        if any(name in med_text for name in beta_blockers):
            alerts.append(
                {
                    "id": "bradycardia-beta-blocker-context",
                    "level": "warning",
                    "title": "Bradycardia with beta blocker context",
                    "message": (
                        f"Heart rate is {heart_rate} bpm and beta blocker therapy "
                        "appears in the medication context."
                    ),
                }
            )

    if glucose is not None and glucose <= 70:
        if any(name in med_text for name in glucose_lowering):
            alerts.append(
                {
                    "id": "hypoglycemia-medication-context",
                    "level": "critical" if glucose <= 55 else "warning",
                    "title": "Low glucose with medication context",
                    "message": (
                        f"Glucose is {glucose} with insulin or glucose-lowering therapy "
                        "in the medication context."
                    ),
                }
            )

    if potassium is not None and potassium >= 5.5:
        if "spironolactone" in med_text and creatinine is not None and creatinine >= 1.45:
            alerts.append(
                {
                    "id": "hyperkalemia-renal-med-context",
                    "level": "critical",
                    "title": "High potassium with renal and medication context",
                    "message": (
                        f"Potassium is {potassium} with creatinine {creatinine}. "
                        "Spironolactone appears in the medication context."
                    ),
                }
            )

    if spo2 is not None and spo2 <= 90 and rr is not None and (rr >= 24 or rr <= 11):
        alerts.append(
            {
                "id": "oxygenation-respiratory-pattern",
                "level": "critical",
                "title": "Low SpO2 with abnormal respiratory rate",
                "message": f"SpO2 is {spo2}% with respiratory rate {rr}/min.",
            }
        )

    if wbc is not None and wbc >= 12 and temp is not None and temp >= 38.0:
        alerts.append(
            {
                "id": "infection-inflammatory-pattern",
                "level": "warning",
                "title": "High WBC with fever pattern",
                "message": f"WBC is {wbc} and temperature is {temp}°C.",
            }
        )

    if glucose is not None and (glucose >= 220 or glucose <= 55):
        alerts.append(
            {
                "id": "abnormal-glucose-trend",
                "level": "critical" if glucose <= 55 else "warning",
                "title": "Abnormal glucose trend",
                "message": f"Glucose is {glucose}. Review trend and medication context.",
            }
        )

    return alerts


def build_interpretation(
    values: dict[str, Any],
    colors: dict[str, str],
    color: str,
    medications: list[dict[str, Any]],
) -> dict[str, str]:
    hr = values["heartRate"]
    rr = values["respiratoryRate"]
    spo2 = values["spo2"]
    glucose = values["glucose"]
    potassium = values["potassium"]
    creatinine = values["creatinine"]
    wbc = values["wbc"]
    temp = values["temperature"]

    med_text = " ".join(
        f"{med.get('name', '')} {med.get('med', '')}".lower()
        for med in medications
    )

    if color == "red":
        title = "(!) Critical abnormalities detected"
    elif color == "yellow":
        title = "(!) Warning abnormalities detected"
    else:
        title = "No critical abnormalities detected"

    rhythm_parts = []

    if colors["heartRate"] in {"red", "yellow"}:
        rhythm_parts.append(f"heart rate is {hr} bpm")

    if colors["potassium"] in {"red", "yellow"}:
        rhythm_parts.append(f"potassium is {potassium} mmol/L")

    if rhythm_parts:
        rhythm = (
            "Latest FHIR-derived values show "
            + " and ".join(rhythm_parts)
            + ". Keep local ECG waveform simulation visible while reviewing rhythm risk."
        )
    else:
        rhythm = f"Heart rate is {hr} bpm and potassium is {potassium} mmol/L."

    if spo2 <= 90 and rr >= 24:
        ppg = (
            f"SpO2 is {spo2}% with respiratory rate {rr}/min. "
            "This increases concern for oxygenation compromise."
        )
    elif spo2 <= 94:
        ppg = f"SpO2 is {spo2}%. Continue monitoring oxygen saturation and PPG waveform quality."
    else:
        ppg = f"SpO2 is {spo2}%. Oxygenation is acceptable by current demo thresholds."

    likely = (
        f"Latest FHIR values show glucose {glucose}, potassium {potassium}, "
        f"creatinine {creatinine}, WBC {wbc}, temperature {temp}, "
        f"respiratory rate {rr}, and SpO2 {spo2}."
    )

    if potassium >= 5.5 and creatinine >= 1.45 and "spironolactone" in med_text:
        likely += (
            " High potassium plus rising creatinine plus spironolactone context "
            "may suggest renal or potassium-retaining medication contribution."
        )

    if wbc >= 12 and temp >= 38.0:
        likely += " High WBC plus fever pattern may suggest infectious or inflammatory stress."

    likely += " This is sandbox/demo clinical decision support, not a production diagnosis."

    return {
        "title": title,
        "rhythm": rhythm,
        "ppg": ppg,
        "likelyEtiology": likely,
    }


def build_field_debug(
    *,
    raw_values: dict[str, Any],
    final_values: dict[str, Any],
    colors: dict[str, str],
    fallback_used: list[str],
    timestamps: dict[str, str],
    sources: dict[str, Any],
) -> dict[str, Any]:
    details = {}

    for field, label in FIELD_LABELS.items():
        came_from_fhir = raw_values.get(field) is not None
        came_from_fallback = field in fallback_used

        if came_from_fhir:
            source_type = "fhir"
        elif came_from_fallback:
            source_type = "fallback"
        else:
            source_type = "missing"

        source = sources.get(field)

        details[field] = {
            "label": label,
            "source": source_type,
            "finalValue": final_values.get(field),
            "rawFhirValue": raw_values.get(field),
            "fallbackUsed": came_from_fallback,
            "timestamp": timestamps.get(field),
            "color": colors.get(field),
            "fhirObservation": source,
        }

    return details



def build_priority_trends(
    values: dict[str, Any],
    colors: dict[str, str],
    timestamps: dict[str, str],
    medications: list[dict[str, Any]],
    fallback_used: list[str],
) -> list[dict[str, Any]]:
    severity_weight = {"red": 100, "yellow": 50, "blue": 0}

    medication_text = " ".join(
        f"{med.get('name', '')} {med.get('med', '')}".lower()
        for med in medications
    )

    priority_fields = [
        "potassium",
        "creatinine",
        "glucose",
        "wbc",
        "spo2",
        "respiratoryRate",
    ]

    trends = []

    for field in priority_fields:
        value = values.get(field)

        if value is None:
            continue

        color = colors.get(field, "blue")
        score = severity_weight.get(color, 0)
        reason = f"{FIELD_LABELS.get(field, field)} is {color}"

        if field == "potassium" and "spironolactone" in medication_text:
            score += 25
            reason = "Potassium abnormality with spironolactone context"

        if field == "creatinine" and values.get("potassium", 0) >= 5.1:
            score += 20
            reason = "Creatinine and potassium pattern may suggest renal contribution"

        if field == "wbc" and values.get("temperature", 0) >= 38.0:
            score += 20
            reason = "WBC abnormality with fever pattern"

        if field in fallback_used:
            score -= 25
            reason += " using fallback demo value"

        demo_trend = [value]

        if isinstance(value, (int, float)):
            demo_trend = [
                round(value * 0.92, 2),
                round(value * 0.96, 2),
                round(value * 0.98, 2),
                value,
            ]

        trends.append(
            {
                "field": field,
                "label": FIELD_LABELS.get(field, field),
                "value": value,
                "displayValue": str(value),
                "color": color,
                "trend": demo_trend,
                "score": score,
                "reason": reason,
                "meta": timestamps.get(field) or "latest FHIR",
            }
        )

    return sorted(trends, key=lambda item: item["score"], reverse=True)[:4]


def to_dashboard_frame(
    observation_bundle: dict[str, Any],
    *,
    provider: str,
    include_debug: bool = False,
    medication_resources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw_values, timestamps, sources, scan_report = extract_dashboard_values(
        observation_bundle,
        provider=provider,
    )

    values, fallback_used = fill_missing_values(raw_values)

    values = {
        "heartRate": round_if_present(values["heartRate"], 0),
        "respiratoryRate": round_if_present(values["respiratoryRate"], 0),
        "spo2": round_if_present(values["spo2"], 0),
        "systolic": round_if_present(values["systolic"], 0),
        "diastolic": round_if_present(values["diastolic"], 0),
        "temperature": round_if_present(values["temperature"], 1),
        "glucose": round_if_present(values["glucose"], 0),
        "potassium": round_if_present(values["potassium"], 1),
        "creatinine": round_if_present(values["creatinine"], 2),
        "wbc": round_if_present(values["wbc"], 1),
    }

    colors = {
        field: classify_field(field, value)
        for field, value in values.items()
    }

    alert_relevant_colors = {
        key: color
        for key, color in colors.items()
        if key not in ["systolic", "diastolic", "temperature"]
    }

    color = overall_color(alert_relevant_colors)

    medication_rows = normalize_medications(medication_resources or [])
    context_alerts = build_context_alerts(values, colors, medication_rows)

    interpretation = build_interpretation(
        values,
        colors,
        color,
        medication_rows,
    )

    latest_timestamp = max(timestamps.values()) if timestamps else now_iso()

    fhir_fields = [
        field
        for field, value in raw_values.items()
        if value is not None
    ]

    missing_raw_fields = [
        field
        for field, value in raw_values.items()
        if value is None
    ]

    field_debug = build_field_debug(
        raw_values=raw_values,
        final_values=values,
        colors=colors,
        fallback_used=fallback_used,
        timestamps=timestamps,
        sources=sources,
    )

    frame = {
        "source": provider,
        "status": "connected",
        "timestamp": latest_timestamp,
        "receivedAt": now_iso(),
        "overallColor": color,
        "dataQuality": {
            "fhirFieldCount": len(fhir_fields),
            "fallbackFieldCount": len(fallback_used),
            "fhirFields": fhir_fields,
            "fallbackFields": fallback_used,
            "missingRawFhirFields": missing_raw_fields,
            "observationCount": scan_report["observationCount"],
            "matchedObservationCount": scan_report["matchedObservationCount"],
        },
        "fallbackUsed": fallback_used,
        "vitals": {
            "heartRate": values["heartRate"],
            "respiratoryRate": values["respiratoryRate"],
            "spo2": values["spo2"],
            "systolic": values["systolic"],
            "diastolic": values["diastolic"],
            "temperature": values["temperature"],
        },
        "labs": {
            "glucose": values["glucose"],
            "potassium": values["potassium"],
            "creatinine": values["creatinine"],
            "wbc": values["wbc"],
        },
        "colors": colors,
        "interpretation": interpretation,
        "contextAlerts": context_alerts,
        "medicationRows": medication_rows,
        "priorityTrends": build_priority_trends(
            values,
            colors,
            timestamps,
            medication_rows,
            fallback_used,
        ),
    }

    if include_debug:
        frame["debug"] = {
            "rawExtractedFhirValues": raw_values,
            "finalDashboardValues": values,
            "fieldDetails": field_debug,
            "fhirScan": scan_report,
        }

    return frame