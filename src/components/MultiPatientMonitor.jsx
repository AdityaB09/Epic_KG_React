import { getVitalAlerts } from "../utils/clinicalEvents";

export default function MultiPatientMonitor({
  patients,
  telemetryMap,
  monitorSlots,
  onDropPatient,
  onRemovePatient
}) {
  return (
    <section className="monitor-page four-monitor-page">
      <header className="four-monitor-header">
        <div>
          <p className="eyebrow">Multi-patient monitor</p>
          <h1>4 Bed Monitoring Wall</h1>
        </div>
        <span>Drag patients from the sidebar into a monitor slot</span>
      </header>

      <div className="four-monitor-grid">
        {monitorSlots.map((patientId, index) => {
          const patient = patients.find((item) => item.id === patientId);

          return (
            <div
              key={index}
              className={`monitor-slot ${patient ? "filled" : "empty"}`}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                const droppedPatientId = event.dataTransfer.getData("patientId");
                if (droppedPatientId) {
                  onDropPatient(index, droppedPatientId);
                }
              }}
            >
              {patient ? (
                <MonitorTile
                  patient={patient}
                  telemetry={telemetryMap[patient.id]}
                  onRemove={() => onRemovePatient(index)}
                />
              ) : (
                <div className="empty-monitor-slot">
                  <strong>Monitor {index + 1}</strong>
                  <p>Drop patient here</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MonitorTile({ patient, telemetry, onRemove }) {
  const alerts = getVitalAlerts(telemetry);
  const critical = alerts.some((alert) => alert.level === "critical");

  return (
    <article className={`monitor-tile ${critical ? "critical" : ""}`}>
      <header>
        <div>
          <strong>{patient.name}</strong>
          <span>{patient.location} • MRN {patient.mrn}</span>
        </div>

        <button onClick={onRemove}>×</button>
      </header>

      <MiniWave telemetry={telemetry} />

      <div className="monitor-vitals monitor-vitals-full">
  <span>HR <strong>{telemetry.heartRate} bpm</strong></span>
  <span>SpO₂ <strong>{telemetry.oxygen}%</strong></span>
  <span>BP <strong>{telemetry.systolic}/{telemetry.diastolic}</strong></span>
  <span>RR <strong>{telemetry.respiratoryRate}/min</strong></span>
  <span>Temp <strong>{telemetry.temperature}°F</strong></span>
</div>

      <p>{telemetry.alert}</p>
    </article>
  );
}

function MiniWave({ telemetry }) {
  const width = 420;
  const height = 120;

  const points = telemetry.ecg
    .map((point, index) => {
      const x = (index / (telemetry.ecg.length - 1)) * width;
      const y = point.y * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`mini-wave ${telemetry.rhythm}`}
      preserveAspectRatio="none"
    >
      <polyline points={points} />
    </svg>
  );
}