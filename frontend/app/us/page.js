import Panel from "@/components/Panel";
import { CrisisCurves, CurveScrubber, TimeSeries, TimeSeries2 } from "@/components/charts";
import {
  crisisCurvesUS,
  curveHistoryUS,
  latestCurve,
  metricLatest,
  metricMonthly,
  ratesMonthly,
  regimes,
} from "@/lib/db";

export const revalidate = 3600;

const xy = (rows) => rows.map((r) => ({ x: r.obs_date, y: +r.value }));

export default async function USPage() {
  const [curve, shape, spread2y, spread3m, reg, nominal, real, corr24, pcaL, pcaS, pcaC, corrIn, corrOut, crises] =
    await Promise.all([
      latestCurve("US"),
      metricLatest("US", "curve_shape"),
      metricMonthly("US", "spread_10y_2y"),
      metricMonthly("US", "spread_10y_3m"),
      regimes("US"),
      ratesMonthly("US_DGS10"),
      metricMonthly("US", "real_yield_10y"),
      metricMonthly("US", "eq_yield_corr_24m"),
      metricLatest("US", "pca_var_level"),
      metricLatest("US", "pca_var_slope"),
      metricLatest("US", "pca_var_curvature"),
      metricLatest("US", "eq_yield_corr_in_recession"),
      metricLatest("US", "eq_yield_corr_out_recession"),
      crisisCurvesUS(),
    ]);
  const history = await curveHistoryUS();

  // overlay nominal 10Y vs 10Y real yield on a common monthly date set
  const realMap = new Map(real.map((r) => [r.obs_date, +r.value]));
  const realVsNominal = nominal
    .filter((r) => realMap.has(r.obs_date))
    .map((r) => ({ x: r.obs_date, a: +r.value, b: realMap.get(r.obs_date) }));

  const shapeColor =
    shape?.label === "inverted" ? "bg-bad/15 text-bad"
      : shape?.label === "flat" ? "bg-warn/15 text-warn"
      : "bg-good/15 text-good";

  return (
    <div className="space-y-6">
      <header>
        <p className="h-eyebrow">United States · full toolkit</p>
        <h1 className="mt-1 text-2xl font-semibold">US Treasury term structure</h1>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="Yield curve"
          subtitle="Constant-maturity yields — drag the scrubber across history"
          explain={{
            country: "US",
            topic: "the shape of the latest US Treasury yield curve",
            facts: {
              as_of: curve.date,
              curve_shape: shape?.label,
              spread_10y_2y: spread2y.at(-1)?.value,
              points: curve.points.map((p) => ({ tenor: p.tenor_label, yield: p.yield })),
            },
          }}
        >
          <div className="mb-3">
            <span className={`badge ${shapeColor}`}>{shape?.label ?? "—"} (latest)</span>
          </div>
          <CurveScrubber history={history} />
        </Panel>

        <Panel
          title="Slope / spreads"
          subtitle="10Y–2Y and 10Y–3M, NBER recessions shaded"
          explain={{
            country: "US",
            topic: "what the US yield-curve slope and its spreads are showing",
            facts: {
              latest_10y_2y: spread2y.at(-1)?.value,
              latest_10y_3m: spread3m.at(-1)?.value,
              curve_shape: shape?.label,
            },
          }}
        >
          <TimeSeries data={xy(spread2y)} yLabel="pp" zeroLine regimes={reg} />
          <p className="mt-2 text-xs text-muted">
            10Y–2Y (blue). Zero line dashed; shaded bands are NBER recessions.
          </p>
        </Panel>

        <Panel
          title="Real vs nominal 10Y"
          subtitle="Nominal yield vs TIPS-implied real yield"
          explain={{
            country: "US",
            topic: "the gap between nominal and real 10-year yields (breakeven inflation)",
            facts: {
              latest_nominal: realVsNominal.at(-1)?.a,
              latest_real: realVsNominal.at(-1)?.b,
              breakeven_approx:
                realVsNominal.at(-1)
                  ? +(realVsNominal.at(-1).a - realVsNominal.at(-1).b).toFixed(2)
                  : null,
            },
          }}
        >
          <TimeSeries2 data={realVsNominal} aLabel="nominal 10Y" bLabel="real 10Y" />
          <p className="mt-2 text-xs text-muted">
            Nominal (blue) vs real (green); the gap is breakeven inflation.
          </p>
        </Panel>

        <Panel
          title="Curve factors (PCA)"
          subtitle="Litterman–Scheinkman decomposition of daily curve changes"
          explain={{
            country: "US",
            topic: "the principal components of the US curve (level, slope, curvature)",
            facts: {
              level_variance: pcaL?.value,
              slope_variance: pcaS?.value,
              curvature_variance: pcaC?.value,
            },
          }}
        >
          <div className="grid grid-cols-3 gap-3">
            <Factor name="Level" v={pcaL?.value} />
            <Factor name="Slope" v={pcaS?.value} />
            <Factor name="Curvature" v={pcaC?.value} />
          </div>
          <p className="mt-3 text-xs text-muted">
            Share of curve-change variance explained by each factor. The level factor
            dominating (~85%) is the expected Litterman–Scheinkman result.
          </p>
        </Panel>

        <Panel
          title="Equity–yield correlation"
          subtitle="Rolling 24m corr of monthly Δ10Y vs S&P 500 returns"
          explain={{
            country: "US",
            topic: "the equity–yield correlation and how it splits across recessions",
            facts: {
              rolling_24m_latest: corr24.at(-1)?.value,
              in_recession: corrIn?.value,
              out_of_recession: corrOut?.value,
            },
          }}
        >
          <TimeSeries data={xy(corr24)} yLabel="ρ" zeroLine color="#3fb27f" />
          <div className="mt-3 flex gap-3 text-sm">
            <RegimeStat label="in recession" v={corrIn?.value} />
            <RegimeStat label="outside" v={corrOut?.value} />
          </div>
          <p className="mt-2 text-xs text-muted">
            The single-sample mean hides the structure — the regime split is shown
            instead, never a lone number.
          </p>
        </Panel>
      </div>

      <section className="space-y-2 pt-2">
        <h2 className="font-medium">Crisis curve behaviour</h2>
        <p className="max-w-3xl text-sm text-muted">
          How the whole curve reshaped through each stress episode — overlaid
          snapshots at pre-stress, peak, and recovery key dates. Watch the slope
          and level shift (bull-steepening as the Fed cut in 2008 and 2020; the
          2013 bear sell-off).
        </p>
        <div className="grid gap-6 lg:grid-cols-3">
          {crises.map((c) => (
            <Panel
              key={c.name}
              title={c.label}
              explain={{
                country: "US",
                topic: `how the US curve reshaped during ${c.label}`,
                facts: {
                  episode: c.label,
                  key_dates: Object.fromEntries(
                    Object.entries(c.dates).map(([k, v]) => [
                      k,
                      {
                        date: v.snapshot_date,
                        y_2y: v.points.find((p) => p.tenor_months === 24)?.yield,
                        y_10y: v.points.find((p) => p.tenor_months === 120)?.yield,
                      },
                    ])
                  ),
                },
              }}
            >
              <CrisisCurves dates={c.dates} />
            </Panel>
          ))}
        </div>
      </section>
    </div>
  );
}

function Factor({ name, v }) {
  const pct = v != null ? Math.round(+v * 100) : 0;
  return (
    <div className="rounded-lg border border-edge bg-ink/40 p-3">
      <p className="h-eyebrow">{name}</p>
      <p className="metric mt-1 text-xl">{v != null ? `${pct}%` : "—"}</p>
      <div className="mt-2 h-1.5 rounded bg-edge">
        <div className="h-1.5 rounded bg-accent" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function RegimeStat({ label, v }) {
  return (
    <div className="rounded-lg border border-edge bg-ink/40 px-3 py-2">
      <span className="text-muted">{label}: </span>
      <span className="metric">{v != null ? (+v).toFixed(2) : "—"}</span>
    </div>
  );
}
