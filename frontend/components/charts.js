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
import { useTheme } from "@/components/Theme";

// Theme-aware chart palette. Data-line colors are shared (they read on both
// backgrounds); only the chrome (grid/axis/tooltip/labels) swaps.
const PALETTE = {
  light: { grid: "#e2e8f0", axis: "#64748b", muted: "#64748b", ttBg: "#ffffff",
           ttBorder: "#e2e8f0", bandLabel: "#b91c1c", zero: "#b45309" },
  dark:  { grid: "#1e2a44", axis: "#8597b5", muted: "#8597b5", ttBg: "#0b1220",
           ttBorder: "#1e2a44", bandLabel: "#e88f95", zero: "#e0b341" },
};
function usePalette() {
  const { theme } = useTheme();
  return PALETTE[theme] || PALETTE.light;
}

const tick = (p) => ({ stroke: p.axis, fontSize: 11 });
const ttStyle = (p) => ({
  background: p.ttBg, border: `1px solid ${p.ttBorder}`, borderRadius: 8, fontSize: 12,
});
const xTitle = (value, fill) => ({
  value, position: "insideBottom", offset: -10, fill, fontSize: 11,
});
const yTitle = (value, fill) => ({
  value, angle: -90, position: "insideLeft", offset: 6, fill,
  fontSize: 11, style: { textAnchor: "middle" },
});

const ms = (d) => new Date(d).getTime();
const yr = (t) => new Date(t).getUTCFullYear();
const fmt = (v, unit) => (v == null ? "—" : `${(+v).toFixed(2)}${unit}`);

// Regime shading bands behind a time series. Red reads on both themes; inlined as
// direct LineChart children (Recharts ignores ReferenceAreas inside a component).
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

export function TimeSeries({
  data, yLabel = "Value", seriesName = "Value", unit = "",
  color = "#5b9dff", zeroLine = false, regimes,
}) {
  const p = usePalette();
  if (!data?.length) return <div className="text-sm text-muted">No data.</div>;
  const series = data.map((d) => ({ t: ms(d.x), y: d.y }));
  const minX = series[0].t, maxX = series[series.length - 1].t;
  return (
    <ResponsiveContainer width="100%" height={264}>
      <LineChart data={series} margin={{ top: 8, right: 12, bottom: 24, left: 4 }}>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" />
        {regimeBands(regimes, minX, maxX)}
        <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tick={tick(p)} minTickGap={48} tickFormatter={yr} label={xTitle("Year", p.muted)} />
        <YAxis tick={tick(p)} width={56} label={yTitle(yLabel, p.muted)} />
        <Tooltip contentStyle={ttStyle(p)} labelStyle={{ color: p.muted }}
          labelFormatter={(t) => new Date(t).toISOString().slice(0, 10)}
          formatter={(v) => [fmt(v, unit), seriesName]} />
        {zeroLine && <ReferenceLine y={0} stroke={p.zero} strokeDasharray="4 4"
          label={{ value: "0", position: "right", fill: p.zero, fontSize: 10 }} />}
        <Line type="monotone" dataKey="y" name={seriesName} stroke={color} dot={false} strokeWidth={1.6} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function TimeSeries2({
  data, aLabel, bLabel, yLabel = "Yield (%)", unit = "%",
  aColor = "#5b9dff", bColor = "#3fb27f",
}) {
  const p = usePalette();
  if (!data?.length) return <div className="text-sm text-muted">No data.</div>;
  const series = data.map((d) => ({ t: ms(d.x), a: d.a, b: d.b }));
  return (
    <ResponsiveContainer width="100%" height={278}>
      <LineChart data={series} margin={{ top: 8, right: 12, bottom: 24, left: 4 }}>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" />
        <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tick={tick(p)} minTickGap={48} tickFormatter={yr} label={xTitle("Year", p.muted)} />
        <YAxis tick={tick(p)} width={56} label={yTitle(yLabel, p.muted)} />
        <Tooltip contentStyle={ttStyle(p)} labelStyle={{ color: p.muted }}
          labelFormatter={(t) => new Date(t).toISOString().slice(0, 10)}
          formatter={(v, n) => [fmt(v, unit), n]} />
        <Legend verticalAlign="top" align="center" height={26}
          wrapperStyle={{ fontSize: 11, color: p.muted, paddingBottom: 8 }} />
        <Line type="monotone" dataKey="a" name={aLabel} stroke={aColor} dot={false} strokeWidth={1.6} />
        <Line type="monotone" dataKey="b" name={bLabel} stroke={bColor} dot={false} strokeWidth={1.6} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// US rates & spread crisis timeline: 10Y, 2Y, 10Y-2Y spread + four crisis bands.
const BAND_LABEL = {
  gfc_2008: "GFC 2008", taper_tantrum: "Taper 2013",
  covid: "COVID 2020", westasia_war_2026: "War 2026",
};

function crisisBandShapes(bands, minX, maxX, labelFill) {
  if (!bands) return null;
  return bands
    .map((b, i) => {
      let x1 = ms(b.start_date);
      let x2 = b.end_date ? ms(b.end_date) : maxX; // open-ended war -> latest data
      if (x2 < minX || x1 > maxX) return null;
      x1 = Math.max(x1, minX);
      x2 = Math.min(x2, maxX);
      return (
        <ReferenceArea key={`cb-${i}`} x1={x1} x2={x2} yAxisId={0}
          fill="#e5616a" fillOpacity={0.16} stroke="#e5616a" strokeOpacity={0.3}
          ifOverflow="hidden"
          label={{ value: BAND_LABEL[b.regime_name] || b.regime_name,
            position: "insideTop", fill: labelFill, fontSize: 9, offset: 6 }} />
      );
    })
    .filter(Boolean);
}

export function RatesTimeline({ data, bands }) {
  const p = usePalette();
  if (!data?.length) return <div className="text-sm text-muted">No data.</div>;
  const series = data.map((d) => ({ t: ms(d.x), y10: d.y10, y2: d.y2, spread: d.spread }));
  const minX = series[0].t, maxX = series[series.length - 1].t;
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={series} margin={{ top: 16, right: 12, bottom: 24, left: 4 }}>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" />
        {crisisBandShapes(bands, minX, maxX, p.bandLabel)}
        <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tick={tick(p)} minTickGap={48} tickFormatter={yr} label={xTitle("Year", p.muted)} />
        <YAxis tick={tick(p)} width={56} label={yTitle("Yield / spread (%)", p.muted)} />
        <Tooltip contentStyle={ttStyle(p)} labelStyle={{ color: p.muted }}
          labelFormatter={(t) => new Date(t).toISOString().slice(0, 10)}
          formatter={(v, n) => [fmt(v, "%"), n]} />
        <Legend verticalAlign="top" align="center" height={26}
          wrapperStyle={{ fontSize: 11, color: p.muted, paddingBottom: 8 }} />
        <ReferenceLine y={0} yAxisId={0} stroke={p.zero} strokeDasharray="4 4"
          label={{ value: "0 = inversion", position: "insideBottomRight",
            fill: p.zero, fontSize: 10 }} />
        <Line type="monotone" dataKey="y10" name="10Y yield" stroke="#5b9dff" dot={false} strokeWidth={1.5} />
        <Line type="monotone" dataKey="y2" name="2Y yield" stroke="#b78bff" dot={false} strokeWidth={1.5} />
        <Line type="monotone" dataKey="spread" name="10Y − 2Y spread" stroke="#3fb27f" dot={false} strokeWidth={1.8} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// Overlay several curves (yield vs maturity) for crisis reshape — one per key date.
const CRISIS_COLORS = { pre_stress: "#8597b5", peak: "#e5616a", recovery: "#3fb27f" };
const CRISIS_LABELS = { pre_stress: "pre-stress", peak: "peak", recovery: "recovery" };

export function CrisisCurves({ dates }) {
  const p = usePalette();
  const order = ["pre_stress", "peak", "recovery"].filter((k) => dates[k]);
  if (!order.length) return <div className="text-sm text-muted">No data.</div>;
  const tenors = dates[order[0]].points.map((pt) => pt.tenor);
  const data = tenors.map((t, i) => {
    const row = { x: t };
    for (const k of order) row[k] = dates[k].points[i]?.yield;
    return row;
  });
  return (
    <>
      <ResponsiveContainer width="100%" height={264}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 24, left: 4 }}>
          <CartesianGrid stroke={p.grid} strokeDasharray="3 3" />
          <XAxis dataKey="x" tick={tick(p)} label={xTitle("Maturity (term of bond)", p.muted)} />
          <YAxis tick={tick(p)} width={56} label={yTitle("Yield (%)", p.muted)} />
          <Tooltip contentStyle={ttStyle(p)} labelStyle={{ color: p.muted }}
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
  const p = usePalette();
  if (!points?.length) return <div className="text-sm text-muted">No data.</div>;
  const data = points.map((pt) => ({ x: pt.tenor_label, y: pt.yield }));
  return (
    <ResponsiveContainer width="100%" height={264}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 24, left: 4 }}>
        <defs>
          <linearGradient id="cv" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5b9dff" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#5b9dff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={p.grid} strokeDasharray="3 3" />
        <XAxis dataKey="x" tick={tick(p)} label={xTitle("Maturity (term of bond)", p.muted)} />
        <YAxis tick={tick(p)} width={56} label={yTitle("Yield (%)", p.muted)} />
        <Tooltip contentStyle={ttStyle(p)} labelStyle={{ color: p.muted }}
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
