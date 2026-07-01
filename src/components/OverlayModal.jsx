export default function OverlayModal({ type, patient, medications, labs, documents, onClose }) {
  const titleMap = {
    medications: "Medications",
    labs: "Lab Results",
    documents: "Documents",
    patient: "Add Patient",
    note: "Add Clinical Note"
  };

  const title = titleMap[type] ?? "Details";

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <aside className="overlay-modal" onMouseDown={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>{title}</h2>
            <p>{patient.name} • MRN {patient.mrn}</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close modal">×</button>
        </header>

        <div className="modal-content">
          {type === "medications" && <MedicationTable medications={medications} />}
          {type === "labs" && <LabTable labs={labs} />}
          {type === "documents" && <DocumentTable documents={documents} />}
          {type === "patient" && <PatientForm />}
          {type === "note" && <NoteForm />}
        </div>

        <footer className="modal-footer">
          <button className="ghost-btn" onClick={onClose}>Cancel</button>
          <button className="primary-btn" onClick={onClose}>
            {type === "patient" || type === "note" ? "Save" : `+ Add ${title}`}
          </button>
        </footer>
      </aside>
    </div>
  );
}

function MedicationTable({ medications }) {
  return (
    <table className="data-table">
      <thead>
        <tr><th>Medication</th><th>Dose</th><th>Frequency</th><th>Prescribed</th><th>Status</th></tr>
      </thead>
      <tbody>
        {medications.map((med) => (
          <tr key={med.id}>
            <td>{med.medication}</td>
            <td>{med.dose}</td>
            <td>{med.frequency}</td>
            <td>{med.prescribed}</td>
            <td>{med.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LabTable({ labs }) {
  return (
    <table className="data-table">
      <thead>
        <tr><th>Test</th><th>Value</th><th>Reference</th><th>Date</th></tr>
      </thead>
      <tbody>
        {labs.map((lab) => (
          <tr key={lab.id}>
            <td>{lab.title}</td>
            <td>{lab.value}</td>
            <td>{lab.reference}</td>
            <td>{lab.date}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DocumentTable({ documents }) {
  return (
    <table className="data-table">
      <thead>
        <tr><th>Document</th><th>Type</th><th>Owner</th><th>Date</th></tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr key={doc.id}>
            <td>{doc.title}</td>
            <td>{doc.type}</td>
            <td>{doc.owner}</td>
            <td>{doc.date}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PatientForm() {
  return (
    <form className="stacked-form">
      <label>Patient name<input placeholder="Enter patient name" /></label>
      <label>MRN<input placeholder="Enter MRN" /></label>
      <label>Unit<select><option>CTU</option><option>CONSULTS</option></select></label>
      <label>Location<input placeholder="Room or bed number" /></label>
    </form>
  );
}

function NoteForm() {
  return (
    <form className="stacked-form">
      <label>Note title<input placeholder="Short title" /></label>
      <label>Clinical note<textarea rows="7" placeholder="Write note here..." /></label>
    </form>
  );
}
