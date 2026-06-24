"use client";

import { useMemo, useState } from "react";
import { compute, PRESETS, type BondResult } from "@/lib/bond";

type Mode = "price" | "yield";

const num = (v: number | null | undefined, d = 4) =>
  v == null || !isFinite(v) ? "—" : v.toFixed(d);

export default function BondCalculator() {
  const [preset, setPreset] = useState<keyof typeof PRESETS>("US_TREASURY");
  const [face, setFace] = useState("100");
  const [couponPct, setCouponPct] = useState("6");
  const [settlement, setSettlement] = useState("2026-01-15");
  const [maturity, setMaturity] = useState("2036-01-15");
  const [mode, setMode] = useState<Mode>("yield");
  const [inputVal, setInputVal] = useState("6");

  const { result, error } = useMemo(() => {
    try {
      const args = {
        faceValue: parseFloat(face),
        couponRate: parseFloat(couponPct) / 100,
        settlement, maturity, preset,
        ...(mode === "yield"
          ? { ytm: parseFloat(inputVal) / 100 }
          : { price: parseFloat(inputVal) }),
      };
      if ([args.faceValue, args.couponRate].some((x) => !isFinite(x))) throw 0;
      if (new Date(maturity) <= new Date(settlement)) throw new Error("maturity must be after settlement");
      return { result: compute(args) as BondResult, error: "" };
    } catch (e: any) {
      return { result: null, error: e?.message || "invalid inputs" };
    }
  }, [face, couponPct, settlement, maturity, preset, mode, inputVal]);

  // Explain (on-demand, reflects current outputs)
  const [exOpen, setExOpen] = useState(false);
  const [exText, setExText] = useState("");
  const [exLoading, setExLoading] = useState(false);

  async function explain() {
    setExOpen(true);
    setExLoading(true);
    setExText("");
    try {
      const facts = {
        preset: PRESETS[preset].label,
        inputs: { face: +face, coupon_pct: +couponPct, settlement, maturity, mode, input: +inputVal },
        outputs: result && {
          clean_price: +result.cleanPrice.toFixed(4),
          dirty_price: +result.dirtyPrice.toFixed(4),
          accrued_interest: +result.accruedInterest.toFixed(4),
          ytm_pct: +(result.yield * 100).toFixed(4),
          current_yield_pct: result.currentYield ? +(result.currentYield * 100).toFixed(4) : null,
          macaulay_duration: +result.macaulayDuration.toFixed(4),
          modified_duration: +result.modifiedDuration.toFixed(4),
          convexity: +result.convexity.toFixed(4),
          dv01: +result.dv01.toFixed(5),
        },
      };
      const res = await fetch("/api/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          country: preset === "INDIA_GSEC" ? "IN" : "US",
          topic: "what this bond's price, yield, duration, convexity and DV01 mean",
          facts,
        }),
      });
      const data = await res.json();
      setExText(res.ok ? data.explanation : data.error);
    } catch (e: any) {
      setExText("Error: " + (e?.message || e));
    } finally {
      setExLoading(false);
    }
  }

  return (
    <section className="card">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="font-medium">Bond calculator</h3>
          <p className="mt-0.5 text-sm text-muted">
            Price ↔ yield, duration, convexity and DV01 for a single bond.
          </p>
        </div>
        <button onClick={explain}
          className="badge shrink-0 border border-edge bg-ink/60 text-accent hover:border-accent">
          Explain
        </button>
      </div>

      {exOpen && (
        <div className="mb-4 w-full rounded-lg border border-edge bg-ink/60 p-3 text-sm leading-relaxed">
          {exLoading && <span className="text-muted">Reading the numbers…</span>}
          {exText && <p className="whitespace-pre-wrap break-words text-[13px] text-fg/90">{exText}</p>}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* inputs */}
        <div className="space-y-3">
          <Field label="Convention">
            <select value={preset} onChange={(e) => setPreset(e.target.value as any)} className="inp">
              <option value="US_TREASURY">US Treasury — ACT/ACT</option>
              <option value="INDIA_GSEC">India G-Sec — 30/360</option>
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Face value"><input className="inp" value={face} onChange={(e) => setFace(e.target.value)} /></Field>
            <Field label="Coupon %"><input className="inp" value={couponPct} onChange={(e) => setCouponPct(e.target.value)} /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Settlement"><input type="date" className="inp" value={settlement} onChange={(e) => setSettlement(e.target.value)} /></Field>
            <Field label="Maturity"><input type="date" className="inp" value={maturity} onChange={(e) => setMaturity(e.target.value)} /></Field>
          </div>
          <Field label="Solve from">
            <div className="flex gap-2">
              <button onClick={() => setMode("yield")} className={`tab ${mode === "yield" ? "tab-on" : ""}`}>Yield → Price</button>
              <button onClick={() => setMode("price")} className={`tab ${mode === "price" ? "tab-on" : ""}`}>Price → Yield</button>
            </div>
          </Field>
          <Field label={mode === "yield" ? "Yield to maturity %" : "Clean price"}>
            <input className="inp" value={inputVal} onChange={(e) => setInputVal(e.target.value)} />
          </Field>
        </div>

        {/* outputs */}
        <div>
          {error ? (
            <div className="missing">{error}</div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <Out label="Clean price" v={num(result?.cleanPrice)} hi />
              <Out label="Dirty price" v={num(result?.dirtyPrice)} />
              <Out label="Yield to maturity" v={result ? num(result.yield * 100, 4) + "%" : "—"} hi />
              <Out label="Accrued interest" v={num(result?.accruedInterest)} />
              <Out label="Current yield" v={result?.currentYield ? num(result.currentYield * 100, 4) + "%" : "—"} />
              <Out label="Macaulay duration" v={num(result?.macaulayDuration)} />
              <Out label="Modified duration" v={num(result?.modifiedDuration)} />
              <Out label="Convexity" v={num(result?.convexity)} />
              <Out label="DV01 (per 100 face)" v={num(result?.dv01, 5)} hi />
            </div>
          )}
        </div>
      </div>

      <style>{`
        .inp { width:100%; background:rgb(var(--c-bg)); border:1px solid rgb(var(--c-edge));
               border-radius:8px; padding:8px 10px; font-size:13px; color:rgb(var(--c-fg)); }
        .inp:focus { outline:none; border-color:rgb(var(--c-accent)); }
        .tab { flex:1; border:1px solid rgb(var(--c-edge)); border-radius:8px; padding:8px;
               font-size:12px; color:rgb(var(--c-muted)); background:transparent; }
        .tab-on { border-color:rgb(var(--c-accent)); color:rgb(var(--c-accent));
                  background:rgb(var(--c-accent) / .1); }
      `}</style>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="h-eyebrow">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function Out({ label, v, hi }: { label: string; v: string; hi?: boolean }) {
  return (
    <div className={`rounded-lg border border-edge p-3 ${hi ? "bg-accent/10" : "bg-ink/40"}`}>
      <p className="h-eyebrow">{label}</p>
      <p className={`metric mt-1 ${hi ? "text-lg text-accent" : "text-base"}`}>{v}</p>
    </div>
  );
}
