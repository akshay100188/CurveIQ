// Single-bond pricing engine — client-side, deterministic, no infra.
// Parity-checked against the Python reference twin (pipeline/bond_reference.py)
// via shared golden vectors (lib/bond.golden.json), tested in lib/bond.test.ts.
//
// Conventions:
//   US Treasury : semi-annual, ACT/ACT (ICMA) day-count.
//   India G-Sec : semi-annual, 30/360 day-count (RBI G-Sec primer + FIMMDA).

export type DayCount = "ACT/ACT" | "30/360";

export interface Bond {
  faceValue: number;
  couponRate: number;   // annual, decimal (0.06 == 6%)
  frequency: number;    // coupons per year
  dayCount: DayCount;
  settlement: Date;
  maturity: Date;
}

export interface BondResult {
  dirtyPrice: number;
  cleanPrice: number;
  accruedInterest: number;
  currentYield: number | null;
  macaulayDuration: number;
  modifiedDuration: number;
  convexity: number;
  dv01: number;
  yield: number;
}

export const PRESETS: Record<string, { frequency: number; dayCount: DayCount; label: string }> = {
  US_TREASURY: { frequency: 2, dayCount: "ACT/ACT", label: "US Treasury (semi-annual, ACT/ACT)" },
  INDIA_GSEC: { frequency: 2, dayCount: "30/360", label: "India G-Sec (semi-annual, 30/360)" },
};

// --- date helpers ----------------------------------------------------------
const MS_DAY = 86_400_000;
const asUTC = (d: Date) => Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());

function daysActual(d1: Date, d2: Date): number {
  return Math.round((asUTC(d2) - asUTC(d1)) / MS_DAY);
}

// US (NASD) 30/360 bond basis with month-end edge handling.
function days30360(d1: Date, d2: Date): number {
  const y1 = d1.getUTCFullYear(), m1 = d1.getUTCMonth() + 1;
  const y2 = d2.getUTCFullYear(), m2 = d2.getUTCMonth() + 1;
  let day1 = d1.getUTCDate(), day2 = d2.getUTCDate();
  if (day1 === 31) day1 = 30;
  if (day2 === 31 && day1 === 30) day2 = 30;
  return (y2 - y1) * 360 + (m2 - m1) * 30 + (day2 - day1);
}

function dayCountDays(d1: Date, d2: Date, dc: DayCount): number {
  return dc === "30/360" ? days30360(d1, d2) : daysActual(d1, d2);
}

function addMonths(d: Date, months: number): Date {
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth() + months;
  const targetY = y + Math.floor(m / 12);
  const targetM = ((m % 12) + 12) % 12;
  const lastDay = new Date(Date.UTC(targetY, targetM + 1, 0)).getUTCDate();
  const day = Math.min(d.getUTCDate(), lastDay);
  return new Date(Date.UTC(targetY, targetM, day));
}

// (prevCoupon, nextCoupon, remaining coupon dates ascending)
function schedule(settle: Date, maturity: Date, freq: number) {
  const step = 12 / freq;
  let cursor = maturity;
  const after: Date[] = [];
  while (asUTC(cursor) > asUTC(settle)) {
    after.push(cursor);
    cursor = addMonths(cursor, -step);
  }
  after.reverse();
  return { prev: cursor, next: after[0], remaining: after };
}

function wAndN(b: Bond) {
  const { prev, next, remaining } = schedule(b.settlement, b.maturity, b.frequency);
  const period = dayCountDays(prev, next, b.dayCount);
  const accruedDays = dayCountDays(prev, b.settlement, b.dayCount);
  return { w: (period - accruedDays) / period, n: remaining.length, accruedDays, period };
}

// --- core ------------------------------------------------------------------
export function priceFromYield(b: Bond, ytm: number): BondResult {
  const i = ytm / b.frequency;
  const cpn = (b.faceValue * b.couponRate) / b.frequency;
  const { w, n, accruedDays, period } = wAndN(b);
  let dirty = 0, macNum = 0, convNum = 0;
  for (let k = 0; k < n; k++) {
    const t = w + k;
    const cf = cpn + (k === n - 1 ? b.faceValue : 0);
    const pv = cf / Math.pow(1 + i, t);
    dirty += pv;
    macNum += (t / b.frequency) * pv;
    convNum += pv * t * (t + 1);
  }
  const accrued = cpn * (accruedDays / period);
  const clean = dirty - accrued;
  const macaulay = macNum / dirty;
  const modified = macaulay / (1 + i);
  const convexity = convNum / (dirty * Math.pow(1 + i, 2) * b.frequency ** 2);
  return {
    dirtyPrice: dirty, cleanPrice: clean, accruedInterest: accrued,
    currentYield: clean ? (b.couponRate * b.faceValue) / clean : null,
    macaulayDuration: macaulay, modifiedDuration: modified,
    convexity, dv01: modified * dirty * 1e-4, yield: ytm,
  };
}

// Solve YTM from clean price. Newton–Raphson with bisection fallback.
export function yieldFromPrice(b: Bond, cleanPrice: number): number {
  const { w, n, accruedDays, period } = wAndN(b);
  const cpn = (b.faceValue * b.couponRate) / b.frequency;
  const targetDirty = cleanPrice + cpn * (accruedDays / period);
  const dirtyAt = (y: number) => {
    const i = y / b.frequency;
    let s = 0;
    for (let k = 0; k < n; k++) s += (cpn + (k === n - 1 ? b.faceValue : 0)) / Math.pow(1 + i, w + k);
    return s;
  };
  let y = Math.max(0.0001, b.couponRate);
  for (let it = 0; it < 100; it++) {
    const r = priceFromYield(b, y);
    const f = r.dirtyPrice - targetDirty;
    if (Math.abs(f) < 1e-10) return y;
    const deriv = -r.modifiedDuration * r.dirtyPrice;
    if (deriv === 0) break;
    const yNew = y - f / deriv;
    if (yNew <= 0 || yNew > 2) break;
    y = yNew;
  }
  let lo = 1e-6, hi = 2.0;
  for (let it = 0; it < 200; it++) {
    const mid = (lo + hi) / 2;
    if (dirtyAt(mid) - targetDirty > 0) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}

export interface ComputeArgs {
  faceValue: number;
  couponRate: number;      // decimal
  settlement: string;      // ISO yyyy-mm-dd
  maturity: string;
  preset: keyof typeof PRESETS;
  price?: number;          // provide either price or ytm
  ytm?: number;            // decimal
}

export function compute(a: ComputeArgs): BondResult {
  const p = PRESETS[a.preset];
  const b: Bond = {
    faceValue: a.faceValue, couponRate: a.couponRate,
    frequency: p.frequency, dayCount: p.dayCount,
    settlement: new Date(a.settlement + "T00:00:00Z"),
    maturity: new Date(a.maturity + "T00:00:00Z"),
  };
  const ytm = a.ytm != null ? a.ytm : yieldFromPrice(b, a.price as number);
  return priceFromYield(b, ytm);
}
