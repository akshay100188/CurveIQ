import Explain from "./Explain";

// Server-rendered panel shell with an optional Explain button.
export default function Panel({ title, subtitle, children, explain }) {
  return (
    <section className="card">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h3 className="font-medium">{title}</h3>
          {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
        </div>
        {explain && <Explain {...explain} />}
      </div>
      {children}
    </section>
  );
}

// A panel intentionally omitted for India, annotated with why.
export function MissingPanel({ title, why }) {
  return (
    <section className="card">
      <h3 className="font-medium text-muted">{title}</h3>
      <div className="missing mt-3">
        <span className="badge bg-warn/15 text-warn">not available</span>
        <p className="mt-2">{why}</p>
      </div>
    </section>
  );
}
