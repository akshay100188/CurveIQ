// Server-side Supabase REST reader. Uses the service key and a schema profile
// header; never imported into client components.
const URL = process.env.SUPABASE_URL;
const KEY = process.env.SUPABASE_SERVICE_KEY;

async function rest(path, { schema = "curveiq" } = {}) {
  if (!URL || !KEY) throw new Error("SUPABASE_URL / SUPABASE_SERVICE_KEY not set");
  const res = await fetch(`${URL}/rest/v1/${path}`, {
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
      "Accept-Profile": schema,
    },
    // computed data is static between batch runs; cache for an hour
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error(`REST ${path} -> ${res.status} ${await res.text()}`);
  return res.json();
}

// --- metric helpers --------------------------------------------------------
export async function metricSeries(country, name) {
  return rest(
    `computed_metrics?country=eq.${country}&metric_name=eq.${name}` +
      `&select=obs_date,value,label&order=obs_date.asc`
  );
}

export async function metricLatest(country, name) {
  const r = await rest(
    `computed_metrics?country=eq.${country}&metric_name=eq.${name}` +
      `&select=obs_date,value,label&order=obs_date.desc&limit=1`
  );
  return r[0] || null;
}

export async function ratesSeries(seriesId) {
  return rest(
    `rates_timeseries?series_id=eq.${seriesId}` +
      `&select=obs_date,value&order=obs_date.asc`
  );
}

// month-end downsampled reads (chart-friendly, < 1000 rows)
export async function metricMonthly(country, name) {
  return rest(
    `v_metric_monthly?country=eq.${country}&metric_name=eq.${name}` +
      `&select=obs_date,value,label&order=obs_date.asc`
  );
}

export async function ratesMonthly(seriesId) {
  return rest(
    `v_rates_monthly?series_id=eq.${seriesId}` +
      `&select=obs_date,value&order=obs_date.asc`
  );
}

export async function latestCurve(country) {
  const latest = await rest(
    `curve_points?country=eq.${country}&select=obs_date&order=obs_date.desc&limit=1`
  );
  if (!latest.length) return { date: null, points: [] };
  const d = latest[0].obs_date;
  const points = await rest(
    `curve_points?country=eq.${country}&obs_date=eq.${d}` +
      `&select=tenor_months,tenor_label,yield&order=tenor_months.asc`
  );
  return { date: d, points };
}

export async function crisisCurvesUS() {
  // each US episode's key-date curves, grouped for overlay charts
  const rows = await rest(
    `v_crisis_curves?select=crisis_name,crisis_label,label,snapshot_date,tenor_months,tenor_label,yield` +
      `&order=crisis_name.asc,tenor_months.asc`
  );
  const byCrisis = new Map();
  for (const r of rows) {
    if (!byCrisis.has(r.crisis_name)) {
      byCrisis.set(r.crisis_name, { name: r.crisis_name, label: r.crisis_label, dates: {} });
    }
    const c = byCrisis.get(r.crisis_name);
    if (!c.dates[r.label]) c.dates[r.label] = { snapshot_date: r.snapshot_date, points: [] };
    c.dates[r.label].points.push({ tenor: r.tenor_label, tenor_months: r.tenor_months, yield: r.yield });
  }
  return [...byCrisis.values()];
}

export async function curveHistoryUS() {
  // quarterly full US curves for the time scrubber
  const rows = await rest(
    `v_curve_quarterly?select=obs_date,tenor_months,tenor_label,yield` +
      `&order=obs_date.asc,tenor_months.asc`
  );
  const byDate = new Map();
  for (const r of rows) {
    if (!byDate.has(r.obs_date)) byDate.set(r.obs_date, []);
    byDate.get(r.obs_date).push({
      tenor_months: r.tenor_months, tenor_label: r.tenor_label, yield: r.yield,
    });
  }
  return [...byDate.entries()].map(([date, points]) => ({ date, points }));
}

export async function regimes(country) {
  return rest(
    `regimes?country=eq.${country}&select=regime_name,start_date,end_date&order=start_date.asc`
  );
}

export async function equityClose(table) {
  // table lives in the core schema (curveiq_sp500 / curveiq_nifty50)
  return rest(`${table}?select=date,close&order=date.asc`, { schema: "core" });
}

export { rest };
