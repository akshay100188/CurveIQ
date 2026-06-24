"use client";

import { useEffect, useState } from "react";

// Full-width narrative block. Mounted by Panel the first time "Explain" is opened;
// fetches once. Sends the panel's topic + the L1 numbers it is showing to
// /api/explain, which retrieves corpus context and asks Claude to narrate —
// grounded strictly in the numbers passed in. Text wraps vertically inside the card.
export default function ExplainOutput({ country, topic, facts }) {
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ country, topic, facts }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "request failed");
        if (!cancelled) setText(data.explanation);
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="w-full rounded-lg border border-edge bg-ink/60 p-3 text-sm leading-relaxed">
      {loading && <span className="text-muted">Reading the numbers…</span>}
      {error && <span className="text-bad">Error: {error}</span>}
      {text && (
        <p className="whitespace-pre-wrap break-words text-[13px] text-fg/90">
          {text}
        </p>
      )}
    </div>
  );
}
