"use client";

import { useState } from "react";

// "Explain" affordance. Sends the panel's topic + the L1 numbers it is showing to
// /api/explain, which retrieves corpus context and asks Claude to narrate — grounded
// strictly in the numbers passed in.
export default function Explain({ country, topic, facts }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  async function run() {
    setOpen(true);
    if (text || loading) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ country, topic, facts }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "request failed");
      setText(data.explanation);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shrink-0">
      <button
        onClick={run}
        className="badge border border-edge bg-ink/60 text-accent hover:border-accent"
      >
        Explain
      </button>
      {open && (
        <div className="mt-3 rounded-lg border border-edge bg-ink/60 p-3 text-sm leading-relaxed text-muted">
          {loading && <span>Reading the numbers…</span>}
          {error && <span className="text-bad">Error: {error}</span>}
          {text && <p className="whitespace-pre-wrap text-[13px] text-slate-200">{text}</p>}
        </div>
      )}
    </div>
  );
}
