export default function TimelineFeed({ events }) {
  return (
    <section className="timeline-panel">
      <header className="timeline-header">
        <p className="eyebrow">Live timeline</p>
        <h2>Clinical feed</h2>
      </header>

      <div className="timeline-list">
        {events.length === 0 ? (
          <p className="timeline-empty">Vitals timeline will appear as changes are detected.</p>
        ) : (
          events.map((event) => (
            <article className="timeline-item" key={event.id}>
              <div className={`timeline-dot ${event.level}`} />

              <div>
                <span>{event.time} • {event.type}</span>
                <strong>{event.title}</strong>
                <p>{event.message}</p>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}