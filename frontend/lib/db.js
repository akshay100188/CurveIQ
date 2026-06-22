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
