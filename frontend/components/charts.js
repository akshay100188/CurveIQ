"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
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

function ttStyle() {
  return {
    background: "#0b1220",
    border: "1px solid #1e2a44",
    borderRadius: 8,
    fontSize: 12,
  };
}

const ms = (d) => new Date(d).getTime();
const yr = (t) => new Date(t).getUTCFullYear();

// Regime shading bands drawn behind a time series (numeric time axis).
function RegimeBands({ regimes, minX, maxX }) {
  if (!regimes) return null;
  return regimes.map((r, i) => {
    let x1 = ms(r.start_date);
    let x2 = r.end_date ? ms(r.end_date) : maxX;
    if (x2 < minX || x1 > maxX) return null;
    x1 = Math.max(x1, minX);
    x2 = Math.min(x2, maxX);
    return (
      <ReferenceArea key={i} x1={x1} x2={x2} fill="#e5616a" fillOpacity={0.12}
        stroke="#e5616a" strokeOpacity={0.25} ifOverflow="extendDomain" />
    );
  });
}

// A single time series with optional zero line + regime shading.
export function TimeSeries({ data, yLabel, color = "#5b9dff", zeroLine = false, regimes }) {
  if (!data?.length) return <div className="text-sm text-muted">No data.</div>;
  const series = data.map((d) => ({ t: ms(d.x), y: d.y }));
  const minX = series[0].t, maxX = series[series.length - 1].t;
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={series} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tick={AXIS} minTickGap={48} tickFormatter={yr} />
        <YAxis tick={AXIS} width={48}
          label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "#8597b5", fontSize: 11 }} />
        <Tooltip contentStyle={ttStyle()} labelStyle={{ color: "#8597b5" }}
          labelFormatter={(t) => new Date(t).toISOString().slice(0, 10)} />
        <RegimeBands regimes={regimes} minX={minX} maxX={maxX} />
        {zeroLine && <ReferenceLine y={0} stroke="#e0b341" strokeDasharray="4 4" />}
        <Line type="monotone" dataKey="y" stroke={color} dot={false} strokeWidth={1.6} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// Two overlaid series (e.g. nominal vs real).
export function TimeSeries2({ data, aLabel, bLabel, aColor = "#5b9dff", bColor = "#3fb27f" }) {
  if (!data?.length) return <div className="text-sm text-muted">No data.</div>;
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="x" tick={AXIS} minTickGap={48} />
        <YAxis tick={AXIS} width={48} />
        <Tooltip contentStyle={ttStyle()} labelStyle={{ color: "#8597b5" }} />
        <Line type="monotone" dataKey="a" name={aLabel} stroke={aColor} dot={false} strokeWidth={1.6} />
        <Line type="monotone" dataKey="b" name={bLabel} stroke={bColor} dot={false} strokeWidth={1.6} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// Curve snapshot: yield vs tenor.
export function CurveSnapshot({ points }) {
  if (!points?.length) return <div className="text-sm text-muted">No data.</div>;
  const data = points.map((p) => ({ x: p.tenor_label, y: p.yield }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <defs>
          <linearGradient id="cv" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5b9dff" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#5b9dff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="x" tick={AXIS} />
        <YAxis tick={AXIS} width={48} />
        <Tooltip contentStyle={ttStyle()} labelStyle={{ color: "#8597b5" }} />
        <Area type="monotone" dataKey="y" stroke="#5b9dff" fill="url(#cv)" strokeWidth={1.8} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
