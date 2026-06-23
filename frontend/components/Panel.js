"use client";

import { useState } from "react";
import ExplainOutput from "./Explain";

// Panel shell. The Explain button lives top-right in the header; its narrative
// renders as a FULL-WIDTH block below the header so the text wraps vertically
// inside the card instead of overflowing horizontally.
export default function Panel({ title, subtitle, children, explain }) {
  const [open, setOpen] = useState(false);
  const [everOpened, setEverOpened] = useState(false);

  function toggle() {
    setOpen((o) => !o);
    setEverOpened(true);
  }

  return (
    <section className="card">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h3 className="font-medium">{title}</h3>
          {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
        </div>
        {explain && (
          <button
            onClick={toggle}
            aria-expanded={open}
            className="badge shrink-0 border border-edge bg-ink/60 text-accent hover:border-accent"
          >
            Explain
          </button>
        )}
      </div>

      {explain && everOpened && (
        <div className={open ? "mb-4" : "hidden"}>
          <ExplainOutput {...explain} />
        </div>
      )}

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
