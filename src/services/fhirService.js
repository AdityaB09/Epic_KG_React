const DEFAULT_FIRELY_BASE_URL = "https://server.fire.ly";

export const FIRELY_BASE_URL =
  import.meta.env.VITE_FIRELY_BASE_URL || DEFAULT_FIRELY_BASE_URL;

const FHIR_HEADERS = {
  Accept: "application/fhir+json, application/json"
};

async function fhirGet(path) {
  const url = `${FIRELY_BASE_URL}${path}`;

  const response = await fetch(url, {
    method: "GET",
    headers: FHIR_HEADERS
  });

  if (!response.ok) {
    throw new Error(`FHIR request failed: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

function getBundleResources(bundle) {
  return bundle?.entry?.map((entry) => entry.resource).filter(Boolean) ?? [];
}

function getHumanName(patient) {
  const name = patient?.name?.[0];
  const given = name?.given?.join(" ") ?? "";
  const family = name?.family ?? "";
  const fullName = `${given} ${family}`.trim();
  return fullName || patient?.id || "Unknown Patient";
}

function getAge(birthDate) {
  if (!birthDate) return "--";

  const birth = new Date(birthDate);
  if (Number.isNaN(birth.getTime())) return "--";

  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const monthDiff = today.getMonth() - birth.getMonth();

  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
    age -= 1;
  }

  return age;
}

function getMrn(patient) {
  const identifiers = patient?.identifier ?? [];
  const mrn = identifiers.find((item) =>
    item?.type?.coding?.some((coding) => coding.code === "MR")
  );

  return mrn?.value || identifiers[0]?.value || patient?.id || "FHIR-ID";
}

function getInitials(name) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "PT";
}

function mapPatient(patient, index) {
  const name = getHumanName(patient);
  const risk = index % 5 === 0 ? "High" : index % 3 === 0 ? "Watch" : "Stable";

  return {
    id: patient.id,
    fhirId: patient.id,
    name,
    age: getAge(patient.birthDate),
    sex: patient.gender ? patient.gender[0].toUpperCase() + patient.gender.slice(1) : "Unknown",
    mrn: getMrn(patient),
    unit: index % 2 === 0 ? "FHIR CTU" : "FHIR CONSULTS",
    location: `FHIR Bed ${index + 1}`,
    allergies: "Check FHIR record",
    status: risk === "High" ? "Urgent" : risk === "Watch" ? "Review" : "Code-Status",
    risk,
    avatar: getInitials(name),
    lastSeen: "FHIR sandbox",
    source: "Firely"
  };
}

function valueToText(resource) {
  if (resource.valueQuantity) {
    const value = resource.valueQuantity.value ?? "";
    const unit = resource.valueQuantity.unit ?? resource.valueQuantity.code ?? "";
    return `${value} ${unit}`.trim();
  }

  if (resource.valueCodeableConcept) {
    return resource.valueCodeableConcept.text || resource.valueCodeableConcept.coding?.[0]?.display || "Codeable value";
  }

  if (resource.valueString) return resource.valueString;
  if (resource.valueBoolean !== undefined) return String(resource.valueBoolean);
  if (resource.valueInteger !== undefined) return String(resource.valueInteger);

  return resource.status || "Available";
}

function displayName(resource) {
  return (
    resource.code?.text ||
    resource.code?.coding?.[0]?.display ||
    resource.medicationCodeableConcept?.text ||
    resource.medicationCodeableConcept?.coding?.[0]?.display ||
    resource.type?.text ||
    resource.type?.coding?.[0]?.display ||
    resource.description ||
    resource.id ||
    "FHIR item"
  );
}

function resourceDate(resource) {
  return (
    resource.effectiveDateTime ||
    resource.authoredOn ||
    resource.date ||
    resource.issued ||
    resource.meta?.lastUpdated ||
    "FHIR sandbox"
  );
}

function shortDate(dateValue) {
  if (!dateValue) return "FHIR sandbox";
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return String(dateValue).slice(0, 16);
  return date.toLocaleDateString();
}

function mapObservation(resource, index) {
  return {
    id: resource.id || `obs-${index}`,
    title: displayName(resource),
    description: resource.status ? `Status: ${resource.status}` : "FHIR Observation",
    value: valueToText(resource),
    reference: resource.category?.[0]?.coding?.[0]?.display || resource.category?.[0]?.text || "Observation",
    date: shortDate(resourceDate(resource))
  };
}

function mapMedication(resource, index) {
  const doseInstruction = resource.dosageInstruction?.[0]?.text || resource.dosage?.[0]?.text || "Check FHIR dosage";

  return {
    id: resource.id || `med-${index}`,
    medication: displayName(resource),
    dose: doseInstruction,
    frequency: resource.dosageInstruction?.[0]?.timing?.code?.text || "FHIR record",
    prescribed: shortDate(resourceDate(resource)),
    status: resource.status || "available"
  };
}

function mapDocument(resource, index) {
  return {
    id: resource.id || `doc-${index}`,
    title: displayName(resource),
    type: resource.content?.[0]?.attachment?.contentType || resource.type?.text || "FHIR DocumentReference",
    owner: resource.author?.[0]?.display || resource.custodian?.display || "FHIR sandbox",
    date: shortDate(resourceDate(resource))
  };
}

export async function fetchFirelyPatients(count = 8) {
  const bundle = await fhirGet(`/Patient?_count=${count}`);
  return getBundleResources(bundle).map(mapPatient);
}

export async function fetchFirelyPatientClinicalData(patientId) {
  if (!patientId) {
    return { observations: [], medications: [], documents: [] };
  }

  const safePatientId = encodeURIComponent(patientId);

  const [observationBundle, medicationBundle, documentBundle] = await Promise.allSettled([
    fhirGet(`/Observation?patient=${safePatientId}&_count=8`),
    fhirGet(`/MedicationRequest?patient=${safePatientId}&_count=8`),
    fhirGet(`/DocumentReference?patient=${safePatientId}&_count=8`)
  ]);

  return {
    observations:
      observationBundle.status === "fulfilled"
        ? getBundleResources(observationBundle.value).map(mapObservation)
        : [],
    medications:
      medicationBundle.status === "fulfilled"
        ? getBundleResources(medicationBundle.value).map(mapMedication)
        : [],
    documents:
      documentBundle.status === "fulfilled"
        ? getBundleResources(documentBundle.value).map(mapDocument)
        : []
  };
}

export async function testFirelyConnection() {
  const metadata = await fhirGet("/metadata");
  return {
    software: metadata.software?.name || "Firely Server",
    version: metadata.fhirVersion || "FHIR",
    status: metadata.status || "active"
  };
}
