import { useEffect, useState } from "react";

export default function WidgetCard({
  title,
  items,
  kind,
  onAdd,
  onSeeAll,
  variant = "brief",
  fullWidth = false,
  defaultExpanded = false,
  resetKey
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  useEffect(() => {
    setExpanded(defaultExpanded);
  }, [resetKey, defaultExpanded]);

  const visibleItems = variant === "brief" ? items.slice(0, 2) : items;

  return (
    <section className={`widget-card ${fullWidth ? "full-width" : ""}`}>
      <header className="widget-header">
        <button className="widget-title-btn" onClick={() => setExpanded((value) => !value)}>
          <strong>{title}</strong>
          <span>{expanded ? "⌃" : "⌄"}</span>
        </button>

        <button className="add-btn" onClick={onAdd}>+ Add</button>
      </header>

      {expanded && (
        <>
          <div className="widget-body">
            {visibleItems.map((item) => (
              <WidgetRow key={item.id} item={item} kind={kind} />
            ))}
          </div>

          <button className="see-all" onClick={onSeeAll}>
            See all {kind === "labs" ? "reports" : kind}
          </button>
        </>
      )}
    </section>
  );
}

function WidgetRow({ item, kind }) {
  if (kind === "medications") {
    return (
      <article className="widget-row">
        <div className="row-icon">💊</div>
        <div>
          <strong>{item.medication}</strong>
          <p>{item.dose}, {item.frequency}</p>
        </div>
        <span className="chevron">›</span>
      </article>
    );
  }

  if (kind === "labs") {
    return (
      <article className="widget-row">
        <div className="row-icon">⌷</div>
        <div>
          <strong>{item.title}</strong>
          <p>{item.description}</p>
        </div>
        <span className="chevron">›</span>
      </article>
    );
  }

  return (
    <article className="widget-row">
      <div className="row-icon">▣</div>
      <div>
        <strong>{item.title}</strong>
        <p>{item.type} • {item.owner}</p>
      </div>
      <span className="chevron">›</span>
    </article>
  );
}