"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const AXIS = { stroke: "#8597b5", fontSize: 11 };
const GRID = "#1e2a44";
const MUTED = "#8597b5";

function ttStyle() {
  return {
    background: "#0b1220",
    border: "1px solid #1e2a44",
    borderRadius: 8,
    fontSize: 12,
  };
}

// axis-title helpers
const xTitle = (value) => ({
  value, position: "insideBottom", offset: -10, fill: MUTED, fontSize: 11,
});
const yTitle = (value) => ({
  value, angle: -90, position: "insideLeft", offset: 6, fill: MUTED,
  fontSize: 11, style: { textAnchor: "middle" },
});

const ms = (d) => new Date(d).getTime();
const yr = (t) => new Date(t).getUTCFullYear();
const fmt = (v, unit) => (v == null ? "—" : `${(+v).toFixed(2)}${unit}`);

// Regime shading bands drawn behind a time series (numeric time axis).
// NOTE: this is a plain function, not a component — its array of <ReferenceArea>
// elements must be inlined directly as LineChart children. Recharts only detects
// ReferenceArea among its *direct* children; a wrapper component is ignored, so
// the bands silently never render.
function regimeBands(regimes, minX, maxX) {
  if (!regimes) return null;
  return regimes
    .map((r, i) => {
      let x1 = ms(r.start_date);
      let x2 = r.end_date ? ms(r.end_date) : maxX;
      if (x2 < minX || x1 > maxX) return null;
      x1 = Math.max(x1, minX);
      x2 = Math.min(x2, maxX);
      return (
        <ReferenceArea key={`rb-${i}`} x1={x1} x2={x2} yAxisId={0}
          fill="#e5616a" fillOpacity={0.22} stroke="#e5616a" strokeOpacity={0.35}
          ifOverflow="hidden" />
      );
    })
    .filter(Boolean);
}

// A single time series over calendar time.
//   yLabel     — y-axis title (e.g. "Yield (%)")
//   seriesName — name shown in the tooltip (e.g. "India 10Y G-Sec yield")
//   unit       — value suffix in the tooltip (e.g. "%", " pp")
export function TimeSeries({
  data, yLabel = "Value", seriesName = "Value", unit = "",
  color = "#5b9dff", zeroLine = false, regimes,
}) {
  if (!data?.length) return <div className="text-sm text-muted">No data.</div>;
  const series = data.map((d) => ({ t: ms(d.x), y: d.y }));
  const minX = series[0].t, maxX = series[series.length - 1].t;
  return (
    <ResponsiveContainer width="100%" height={264}>
      <LineChart data={series} margin={{ top: 8, right: 12, bottom: 24, left: 4 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        {regimeBands(regimes, minX, maxX)}
        <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tick={AXIS} minTickGap={48} tickFormatter={yr} label={xTitle("Year")} />
        <YAxis tick={AXIS} width={56} label={yTitle(yLabel)} />
        <Tooltip contentStyle={ttStyle()} labelStyle={{ color: MUTED }}
          labelFormatter={(t) => new Date(t).toISOString().slice(0, 10)}
          formatter={(v) => [fmt(v, unit), seriesName]} />
        {zeroLine && <ReferenceLine y={0} stroke="#e0b341" strokeDasharray="4 4"
          label={{ value: "0", position: "right", fill: "#e0b341", fontSize: 10 }} />}
        <Line type="monotone" dataKey="y" name={seriesName} stroke={color} dot={false} strokeWidth={1.6} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// Two overlaid time series (e.g. nominal vs real yield).
export function TimeSeries2({
  data, aLabel, bLabel, yLabel = "Yield (%)", unit = "%",
  aColor = "#5b9dff", bColor = "#3fb27f",
}) {
  if (!data?.length) return <div className="text-sm text-muted">No data.</div>;
  const series = data.map((d) => ({ t: ms(d.x), a: d.a, b: d.b }));
  return (
    <ResponsiveContainer width="100%" height={278}>
      <LineChart data={series} margin={{ top: 8, right: 12, bottom: 24, left: 4 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tick={AXIS} minTickGap={48} tickFormatter={yr} label={xTitle("Year")} />
        <YAxis tick={AXIS} width={56} label={yTitle(yLabel)} />
        <Tooltip contentStyle={ttStyle()} labelStyle={{ color: MUTED }}
          labelFormatter={(t) => new Date(t).toISOString().slice(0, 10)}
          formatter={(v, n) => [fmt(v, unit), n]} />
        <Legend wrapperStyle={{ fontSize: 11, color: MUTED }} />
        <Line type="monotone" dataKey="a" name={aLabel} stroke={aColor} dot={false} strokeWidth={1.6} />
        <Line type="monotone" dataKey="b" name={bLabel} stroke={bColor} dot={false} strokeWidth={1.6} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// Overlay several curves (yield vs maturity) for crisis reshape — one line per key date.
const CRISIS_COLORS = { pre_stress: "#8597b5", peak: "#e5616a", recovery: "#3fb27f" };
const CRISIS_LABELS = { pre_stress: "pre-stress", peak: "peak", recovery: "recovery" };

export function CrisisCurves({ dates }) {
  const order = ["pre_stress", "peak", "recovery"].filter((k) => dates[k]);
  if (!order.length) return <div className="text-sm text-muted">No data.</div>;
  // merge by tenor into one row set: { x: tenorLabel, pre_stress, peak, recovery }
  const tenors = dates[order[0]].points.map((p) => p.tenor);
  const data = tenors.map((t, i) => {
    const row = { x: t };
    for (const k of order) row[k] = dates[k].points[i]?.yield;
    return row;
  });
  return (
    <>
      <ResponsiveContainer width="100%" height={264}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 24, left: 4 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey="x" tick={AXIS} label={xTitle("Maturity (term of bond)")} />
          <YAxis tick={AXIS} width={56} label={yTitle("Yield (%)")} />
          <Tooltip contentStyle={ttStyle()} labelStyle={{ color: MUTED }}
            labelFormatter={(l) => `Maturity: ${l}`}
            formatter={(v, n) => [fmt(v, "%"), CRISIS_LABELS[n] || n]} />
          {order.map((k) => (
            <Line key={k} type="monotone" dataKey={k} name={CRISIS_LABELS[k]}
              stroke={CRISIS_COLORS[k]} dot={false} strokeWidth={1.8} />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
        {order.map((k) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: CRISIS_COLORS[k] }} />
            {CRISIS_LABELS[k]} · {dates[k].snapshot_date}
          </span>
        ))}
      </div>
    </>
  );
}

// Curve snapshot: yield (y) vs maturity (x). One date's observed yields by bond term.
export function CurveSnapshot({ points }) {
  if (!points?.length) return <div className="text-sm text-muted">No data.</div>;
  const data = points.map((p) => ({ x: p.tenor_label, y: p.yield }));
  return (
    <ResponsiveContainer width="100%" height={264}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 24, left: 4 }}>
        <defs>
          <linearGradient id="cv" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5b9dff" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#5b9dff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="x" tick={AXIS} label={xTitle("Maturity (term of bond)")} />
        <YAxis tick={AXIS} width={56} label={yTitle("Yield (%)")} />
        <Tooltip contentStyle={ttStyle()} labelStyle={{ color: MUTED }}
          labelFormatter={(l) => `Maturity: ${l}`}
          formatter={(v) => [fmt(v, "%"), "Yield"]} />
        <Area type="monotone" dataKey="y" name="Yield" stroke="#5b9dff" fill="url(#cv)" strokeWidth={1.8} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Curve snapshot + a time scrubber across quarterly history.
export function CurveScrubber({ history }) {
  const [idx, setIdx] = useState(history.length - 1);
  if (!history?.length) return <div className="text-sm text-muted">No data.</div>;
  const snap = history[Math.min(idx, history.length - 1)];
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-muted">Observed yields by maturity on</span>
        <span className="metric text-accent">{snap.date}</span>
      </div>
      <p className="mb-2 text-xs text-muted">
        A snapshot of that single day — the x-axis is the bond&apos;s term (1 month → 30 years),
        not time. Not a forecast.
      </p>
      <CurveSnapshot points={snap.points} />
      <input
        type="range" min={0} max={history.length - 1} value={idx}
        onChange={(e) => setIdx(+e.target.value)}
        className="mt-3 w-full accent-accent"
        aria-label="Drag to change the snapshot date"
      />
      <div className="mt-1 flex justify-between text-xs text-muted">
        <span>← earlier · {history[0].date}</span>
        <span>{history[history.length - 1].date} · latest →</span>
      </div>
    </div>
  );
}
