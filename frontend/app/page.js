import Link from "next/link";
import { metricLatest } from "@/lib/db";

export const revalidate = 3600;

async function snapshot() {
  const [usShape, usSpread, inSpread] = await Promise.all([
    metricLatest("US", "curve_shape"),
    metricLatest("US", "spread_10y_2y"),
    metricLatest("IN", "spread_10y_short"),
  ]);
  return { usShape, usSpread, inSpread };
}

export default async function Home() {
  const { usShape, usSpread, inSpread } = await snapshot();
  return (
    <div className="space-y-10">
      <section className="pt-6">
        <p className="h-eyebrow">Descriptive yield-curve analytics</p>
        <h1 className="mt-2 max-w-2xl text-3xl font-semibold leading-tight">
          The term structure of US and Indian government rates, computed exactly and
          explained plainly.
        </h1>
        <p className="mt-3 max-w-2xl text-muted">
          Every number is produced by a deterministic, unit-tested compute layer.
          Narration is grounded strictly in those numbers — never advice, never a
          forecast.
        </p>
        <div className="mt-6 flex gap-3">
          <Link href="/us" className="badge bg-accent/15 text-accent ring-1 ring-accent/30">
            Explore US →
          </Link>
          <Link href="/in" className="badge bg-good/15 text-good ring-1 ring-good/30">
            Explore India →
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <Stat label="US curve shape" value={usShape?.label ?? "—"}
          sub={usShape ? `as of ${usShape.obs_date}` : ""} />
        <Stat label="US 10Y–2Y spread"
          value={usSpread ? `${(+usSpread.value).toFixed(2)} pp` : "—"}
          sub={usSpread ? `as of ${usSpread.obs_date}` : ""} />
        <Stat label="India 10Y–short spread"
          value={inSpread ? `${(+inSpread.value).toFixed(2)} pp` : "—"}
          sub={inSpread ? `as of ${inSpread.obs_date}` : ""} />
      </section>

      <section className="card">
        <h2 className="font-medium">The US / India asymmetry</h2>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          The US view is the full toolkit — an eleven-tenor curve, real yields and
          breakevens, official spreads, NBER recession shading, and the curve's
          principal components. The India view is a deliberately smaller companion:
          free data gives a 10-year benchmark and a short rate, so panels that need a
          full curve, an inflation-linked market, or official recession dates are
          shown as absent, each annotated with why. The contrast is the point.
        </p>
      </section>
    </div>
  );
}

function Stat({ label, value, sub }) {
  return (
    <div className="card">
      <p className="h-eyebrow">{label}</p>
      <p className="metric mt-2 text-2xl">{value}</p>
      <p className="mt-1 text-xs text-muted">{sub}</p>
    </div>
  );
}
