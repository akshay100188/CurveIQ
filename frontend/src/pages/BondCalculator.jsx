import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { calculateBond } from '../api/bond.js'
import { useNavigate } from 'react-router-dom'
import ErrorMsg from '../components/ErrorMsg.jsx'
import { ArrowRight } from 'lucide-react'

function Field({ label, name, value, onChange, placeholder, step = '0.01' }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        type="number" step={step} name={name} value={value}
        onChange={onChange} placeholder={placeholder}
        className="input-field"
      />
    </div>
  )
}

function ResultRow({ label, value, accent }) {
  return (
    <div className="flex justify-between items-center py-2.5 border-b border-surface-700 last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <span className={`text-sm font-semibold ${accent || 'text-gray-800'}`}>{value}</span>
    </div>
  )
}

const DEFAULTS = { face_value: 1000, coupon_rate: 5, maturity_years: 10, ytm: 4 }

export default function BondCalculator() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('ytm')
  const [form, setForm] = useState(DEFAULTS)
  const [result, setResult] = useState(null)

  const mutation = useMutation({
    mutationFn: calculateBond,
    onSuccess: (data) => setResult({ ...data.metrics, calculation_id: data.calculation_id }),
  })

  const set = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const handleSubmit = (e) => {
    e.preventDefault()
    const payload = {
      face_value:     Number(form.face_value),
      coupon_rate:    Number(form.coupon_rate) / 100,
      maturity_years: Number(form.maturity_years),
    }
    if (mode === 'ytm') payload.ytm   = Number(form.ytm) / 100
    else                payload.price = Number(form.price)
    mutation.mutate(payload)
  }

  const fmt = (v, d = 4) => v != null ? Number(v).toFixed(d) : '—'

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Bond Calculator</h1>
        <p className="text-xs text-gray-400 mt-1">Semi-annual compounding · Price, YTM, Duration, DV01</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Form */}
        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Face Value ($)" name="face_value" value={form.face_value} onChange={set} placeholder="1000" step="100" />
            <Field label="Coupon Rate (%)" name="coupon_rate" value={form.coupon_rate} onChange={set} placeholder="5" />
            <Field label="Maturity (Years)" name="maturity_years" value={form.maturity_years} onChange={set} placeholder="10" step="0.5" />

            <div>
              <div className="flex gap-2 mb-3">
                <button type="button" onClick={() => setMode('ytm')}
                  className={`flex-1 text-xs py-1.5 rounded-lg transition-colors ${mode === 'ytm' ? 'bg-blue-600 text-white' : 'btn-ghost'}`}>
                  Given YTM → Price
                </button>
                <button type="button" onClick={() => setMode('price')}
                  className={`flex-1 text-xs py-1.5 rounded-lg transition-colors ${mode === 'price' ? 'bg-blue-600 text-white' : 'btn-ghost'}`}>
                  Given Price → YTM
                </button>
              </div>
              {mode === 'ytm'
                ? <Field label="YTM (%)" name="ytm" value={form.ytm} onChange={set} placeholder="4" />
                : <Field label="Price ($)" name="price" value={form.price || ''} onChange={set} placeholder="1081.76" />
              }
            </div>

            {mutation.isError && <ErrorMsg message={mutation.error?.message} />}
            <button type="submit" disabled={mutation.isPending} className="btn-primary w-full">
              {mutation.isPending ? 'Calculating…' : 'Calculate'}
            </button>
          </form>
        </div>

        {/* Results */}
        <div className="card">
          <div className="text-sm font-semibold text-gray-700 mb-4">Results</div>
          {!result && !mutation.isPending && (
            <p className="text-xs text-gray-400">Enter bond parameters and click Calculate.</p>
          )}
          {mutation.isPending && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <div className="w-4 h-4 border-2 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
              Computing…
            </div>
          )}
          {result && (
            <>
              <ResultRow label="Price"             value={`$${fmt(result.price, 2)}`}                                          accent="text-blue-600" />
              <ResultRow label="YTM"               value={`${fmt(result.ytm != null ? result.ytm * 100 : null, 4)}%`} />
              <ResultRow label="Duration"          value={`${fmt(result.duration, 4)} yrs`} />
              <ResultRow label="Modified Duration" value={`${fmt(result.modified_duration, 4)}`} />
              <ResultRow label="Convexity"         value={fmt(result.convexity, 4)} />
              <ResultRow label="DV01"              value={`$${fmt(result.dv01, 4)}`}                                            accent="text-amber-600" />

              <button
                onClick={() => navigate('/scenario-engine', { state: { bondResult: result, formInputs: form } })}
                className="btn-primary w-full mt-4 flex items-center justify-center gap-2"
              >
                Run Scenario Analysis <ArrowRight size={14} />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
