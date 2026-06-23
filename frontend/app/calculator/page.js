import BondCalculator from "@/components/BondCalculator";

export const metadata = { title: "CurveIQ — bond calculator" };

export default function CalculatorPage() {
  return (
    <div className="space-y-6">
      <header>
        <p className="h-eyebrow">Foundational primitive</p>
        <h1 className="mt-1 text-2xl font-semibold">Bond calculator</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Where a yield and a basis-point move become concrete. A deterministic
          single-bond engine — the same math the curve panels rest on — with US
          Treasury (ACT/ACT) and India G-Sec (30/360) day-count conventions.
        </p>
      </header>
      <BondCalculator />
    </div>
  );
}
