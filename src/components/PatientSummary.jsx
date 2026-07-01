export default function PatientSummary({ patient }) {
  return (
    <section className="patient-summary">
      <div>
        <h2>{patient.name}</h2>
        <p>{patient.age} {patient.sex}</p>
      </div>
      <div>
        <span>MRN</span>
        <strong>{patient.mrn}</strong>
      </div>
      <div>
        <span>Location</span>
        <strong>{patient.location}</strong>
      </div>
      <div>
        <span>Allergies</span>
        <strong>{patient.allergies}</strong>
      </div>
      <div>
        <span className={`status-pill ${patient.risk.toLowerCase()}`}>{patient.status}</span>
        <p>{patient.risk}</p>
      </div>
    </section>
  );
}
