export default function AlertPanel({ alerts }) {
  if (!alerts.length) {
    return (
      <section className="alert-panel calm">
        <strong>No active alerts</strong>
        <p>Current vitals are within the expected monitoring range.</p>
      </section>
    );
  }

  return (
    <section className="alert-panel">
      {alerts.map((alert) => (
        <article key={alert.id} className={`alert-card ${alert.level}`}>
          <div className="alert-icon">
            {alert.level === "critical" ? "!" : "⚠"}
          </div>

          <div>
            <strong>{alert.title}</strong>
            <p>{alert.message}</p>
          </div>

          <span>Now</span>
        </article>
      ))}
    </section>
  );
}