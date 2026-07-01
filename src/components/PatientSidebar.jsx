import { useMemo, useState } from "react";

export default function PatientSidebar({
  patients,
  selectedPatientId,
  onSelectPatient,
  onAddPatient,
  collapsed
})  {
  const [query, setQuery] = useState("");

  const groupedPatients = useMemo(() => {
    const filtered = patients.filter((patient) =>
      `${patient.name} ${patient.mrn} ${patient.unit}`.toLowerCase().includes(query.toLowerCase())
    );

    return filtered.reduce((groups, patient) => {
      groups[patient.unit] = groups[patient.unit] || [];
      groups[patient.unit].push(patient);
      return groups;
    }, {});
  }, [patients, query]);

  return (
    <aside className={`patient-sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-header">
        <h2>Patient directory</h2>
        <p>Search among {patients.length} patients</p>

        <label className="sidebar-search">
          <span>⌕</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search all patients"
          />
          <kbd>⌘K</kbd>
        </label>
      </div>

      <div className="patient-list">
        {Object.entries(groupedPatients).map(([unit, unitPatients]) => (
          <section key={unit} className="patient-group">
            <div className="group-title">
              <span>{unit}</span>
              <small>({unitPatients.length} patients)</small>
              <button onClick={onAddPatient} aria-label={`Add patient to ${unit}`}>+</button>
            </div>

            {unitPatients.map((patient) => (
              <button
  key={patient.id}
  draggable
  onDragStart={(event) => {
    event.dataTransfer.setData("patientId", patient.id);
  }}
  className={`patient-row ${selectedPatientId === patient.id ? "selected" : ""}`}
  onClick={() => onSelectPatient(patient.id)}
>
                <div className="avatar">{patient.avatar}</div>
                <div>
                  <strong>{patient.name}</strong>
                  <span>{patient.age} {patient.sex[0]} | MRN: {patient.mrn}</span>
                </div>
                <small>{patient.lastSeen}</small>
              </button>
            ))}
          </section>
        ))}

        {Object.keys(groupedPatients).length === 0 && (
          <p className="empty-state">No patient found. Try a name, unit or MRN.</p>
        )}
      </div>
    </aside>
  );
}
