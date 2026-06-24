import Panel, { MissingPanel } from "@/components/Panel";
import { TimeSeries } from "@/components/charts";
import { metricLatest, metricMonthly, ratesMonthly, regimes } from "@/lib/db";

export const revalidate = 3600;

const xy = (rows) => rows.map((r) => ({ x: r.obs_date, y: +r.value }));

export default async function IndiaPage() {
  const [tenY, spread, repo, nifty, reg, corr24, corrIn, corrOut] = await Promise.all([
    ratesMonthly("IN_10Y_GSEC"),
    metricMonthly("IN", "spread_10y_short"),
    ratesMonthly("IN_REPO_RATE"),
    ratesMonthly("IN_NIFTY50"),
    regimes("IN"),
    metricMonthly("IN", "eq_yield_corr_24m"),
    metricLatest("IN", "eq_yield_corr_in_crisis"),
    metricLatest("IN", "eq_yield_corr_out_crisis"),
  ]);

  return (
    <div className="space-y-6">
      <header>
        <p className="h-eyebrow">India · constrained companion</p>
        <h1 className="mt-1 text-2xl font-semibold">India government rates</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Free data gives a 10-year benchmark and a short rate — not a full curve.
          The panels below are the honest subset; three US panels are shown as absent,
          each with the reason.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="10Y G-Sec yield over time"
          subtitle="India's 10-year benchmark yield, monthly. Red bands = crisis windows."
          explain={{
            country: "IN",
            topic: "the level and history of India's 10-year government bond yield",
            facts: { latest_10y: tenY.at(-1)?.value, as_of: tenY.at(-1)?.obs_date },
          }}
        >
          <TimeSeries data={xy(tenY)} yLabel="Yield (%)"
            seriesName="India 10Y G-Sec yield" unit="%" regimes={reg} color="#3fb27f" />
        </Panel>

        <Panel
          title="Curve slope (10Y minus short rate)"
          subtitle="Long yield minus the short rate, over time. Below 0 = inverted."
          explain={{
            country: "IN",
            topic: "what India's 10Y-minus-short-rate slope shows and why inversions mean less here",
            facts: { latest_spread: spread.at(-1)?.value, as_of: spread.at(-1)?.obs_date },
          }}
        >
          <TimeSeries data={xy(spread)} yLabel="Spread (pp)"
            seriesName="10Y minus short-rate spread" unit=" pp" zeroLine regimes={reg} />
          <p className="mt-2 text-xs text-muted">
            Percentage points (10Y G-Sec − short rate). India inversions are rare and
            carry little recession content — see Explain.
          </p>
        </Panel>

        <Panel
          title="Policy rate (administered)"
          subtitle="RBI repo rate — set by the central bank, not a traded market price"
          explain={{
            country: "IN",
            topic: "why the RBI repo rate is shown separately as an administered rate",
            facts: { latest_repo: repo.at(-1)?.value, as_of: repo.at(-1)?.obs_date },
          }}
        >
          <span className="badge mb-3 bg-warn/15 text-warn">administered</span>
          <TimeSeries data={xy(repo)} yLabel="Rate (%)"
            seriesName="RBI repo rate" unit="%" color="#e0b341" />
        </Panel>

        <Panel
          title="Stocks vs yields (correlation)"
          subtitle="24-month rolling correlation: monthly 10Y change vs Nifty 50 return"
          explain={{
            country: "IN",
            topic: "the equity–yield correlation in India split across crisis windows",
            facts: {
              rolling_24m_latest: corr24.at(-1)?.value,
              in_crisis: corrIn?.value,
              out_of_crisis: corrOut?.value,
            },
          }}
        >
          <TimeSeries data={xy(corr24)} yLabel="Correlation (−1 to +1)"
            seriesName="24-month rolling correlation" zeroLine color="#3fb27f" />
          <div className="mt-3 flex gap-3 text-sm">
            <div className="rounded-lg border border-edge bg-ink/40 px-3 py-2">
              <span className="text-muted">during crises: </span>
              <span className="metric">{corrIn?.value != null ? (+corrIn.value).toFixed(2) : "—"}</span>
            </div>
            <div className="rounded-lg border border-edge bg-ink/40 px-3 py-2">
              <span className="text-muted">outside crises: </span>
              <span className="metric">{corrOut?.value != null ? (+corrOut.value).toFixed(2) : "—"}</span>
            </div>
          </div>
          <p className="mt-2 text-xs text-muted">
            Correlation runs −1 to +1 (0 = no relationship), split by regime.
          </p>
        </Panel>

        <MissingPanel
          title="Full yield curve"
          why="India's free data gives only a 10-year benchmark and a short rate. A full multi-tenor curve (and the CCIL curve) is paid, so there is no curve-shape classification or PCA here."
        />
        <MissingPanel
          title="Real yield / breakeven"
          why="India has no liquid inflation-linked bond market comparable to US TIPS, so a real-yield and breakeven-inflation decomposition cannot be derived from free data."
        />
        <MissingPanel
          title="Official recession shading"
          why="There is no Indian equivalent of the NBER's official recession dates. The crisis windows shown (Taper Tantrum 2013, COVID 2020) are hard-coded constants, not an official series."
        />
      </div>

      <section className="space-y-2 pt-2">
        <h2 className="font-medium">Crisis behaviour</h2>
        <p className="max-w-3xl text-sm text-muted">
          With no free curve, India can&apos;t show a curve reshape like the US.
          Instead these zoom into each crisis window to show the 10Y level
          trajectory — the honest degraded view. Only the 2013 and 2020 episodes
          appear: the 2008 GFC shown on the US page is{" "}
          <span className="text-slate-300">absent here because Indian G-Sec data
          in this app starts around 2011</span> — a direct instance of the
          data-availability asymmetry, not an oversight.
        </p>
        <div className="grid gap-6 lg:grid-cols-2">
          {reg.map((w) => {
            const slice = tenY
              .filter((r) => r.obs_date >= w.start_date && (!w.end_date || r.obs_date <= w.end_date))
              .map((r) => ({ x: r.obs_date, y: +r.value }));
            return (
              <Panel
                key={w.regime_name}
                title={w.regime_name === "taper_tantrum" ? "Taper Tantrum (2013)" : "COVID shock (2020)"}
                subtitle={`India 10Y G-Sec yield, ${w.start_date} → ${w.end_date || "ongoing"}`}
                explain={{
                  country: "IN",
                  topic: `India's 10Y trajectory through the ${w.regime_name} window and why only a level view is possible`,
                  facts: {
                    window: { start: w.start_date, end: w.end_date },
                    points: slice.map((p) => ({ date: p.x, y_10y: p.y })),
                  },
                }}
              >
                <TimeSeries data={slice} yLabel="Yield (%)"
                  seriesName="India 10Y G-Sec yield" unit="%" color="#3fb27f" />
                <p className="mt-2 text-xs text-muted">
                  No curve-shift view is possible — India has no free full curve.
                </p>
              </Panel>
            );
          })}
        </div>
      </section>
    </div>
  );
}
