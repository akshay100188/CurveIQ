import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { runScenario } from '../api/bond.js'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import ErrorMsg from '../components/ErrorMsg.jsx'
import Spinner  from '../components/Spinner.jsx'

function fmt(v, d = 2) { return v != null ? Number(v).toFixed(d) : '—' }

const SHOCK_LABELS = { '-200': '-200bps', '-100': '-100bps', '-50': '-50bps', '50': '+50bps', '100': '+100bps', '200': '+200bps' }

export default function ScenarioEngine() {
  const { state } = useLocation()
  const [scenarios, setScenarios] = useState(null)
  const [shocks, setShocks] = useState('[-200,-100,-50,50,100,200]')

  const mutation = useMutation({
    mutationFn: runScenario,
    onSuccess: (data) => setScenarios(data.scenarios),
  })

  useEffect(() => {
    if (state?.bondResult?.calculation_id) {
      mutation.mutate({
        bond_calculation_id: state.bondResult.calculation_id,
        shocks_bps: [-200, -100, -50, 50, 100, 200],
      })
    }
  }, [])  // eslint-disable-line

  const handleManual = (e) => {
    e.preventDefault()
    const fd = new FormData(e.target)
    try {
      const parsedShocks = JSON.parse(shocks)
      mutation.mutate({
        face_value:     Number(fd.get('face_value')),
        coupon_rate:    Number(fd.get('coupon_rate')) / 100,
        maturity_years: Number(fd.get('maturity_years')),
        ytm:            Number(fd.get('ytm')) / 100,
        shocks_bps:     parsedShocks,
      })
    } catch { alert('Invalid shocks format') }
  }

  const chartData = (scenarios || []).map(s => ({
    shock: SHOCK_LABELS[String(s.shock_bps)] || `${s.shock_bps > 0 ? '+' : ''}${s.shock_bps}bps`,
    pct:   Number(s.price_change_pct),
  }))

  const tooltipStyle = { background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.07)' }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Scenario Engine</h1>
        <p className="text-xs text-gray-400 mt-1">Rate shock impact · Duration + convexity approximation</p>
      </div>

      {/* Manual input when not pre-populated */}
      {!state?.bondResult && (
        <div className="card max-w-lg">
          <div className="text-sm font-semibold text-gray-700 mb-4">Bond Parameters</div>
          <form onSubmit={handleManual} className="grid grid-cols-2 gap-3">
            {[
              ['face_value',     'Face Value ($)',    '1000'],
              ['coupon_rate',    'Coupon Rate (%)',   '5'],
              ['maturity_years', 'Maturity (Years)',  '10'],
              ['ytm',            'YTM (%)',           '4'],
            ].map(([n, l, p]) => (
              <div key={n}>
                <label className="label">{l}</label>
                <input name={n} type="number" step="0.0001" placeholder={p} defaultValue={p} className="input-field" />
              </div>
            ))}
            <div className="col-span-2">
              <label className="label">Shocks (bps JSON array)</label>
              <input value={shocks} onChange={e => setShocks(e.target.value)} className="input-field" />
            </div>
            {mutation.isError && <div className="col-span-2"><ErrorMsg message={mutation.error?.message} /></div>}
            <div className="col-span-2">
              <button type="submit" disabled={mutation.isPending} className="btn-primary w-full">
                {mutation.isPending ? 'Running…' : 'Run Scenarios'}
              </button>
            </div>
          </form>
        </div>
      )}

      {state?.bondResult && (
        <div className="card border-blue-200 bg-blue-50">
          <div className="text-xs text-gray-500 mb-2">Bond from Calculator</div>
          <div className="flex gap-6 text-xs">
            <span>Price: <span className="text-blue-600 font-semibold">${fmt(state.bondResult.price, 2)}</span></span>
            <span>YTM: <span className="text-gray-700 font-medium">{fmt(state.bondResult.ytm != null ? state.bondResult.ytm * 100 : null, 4)}%</span></span>
            <span>Mod. Duration: <span className="text-gray-700 font-medium">{fmt(state.bondResult.modified_duration, 4)}</span></span>
            <span>DV01: <span className="text-amber-600 font-medium">${fmt(state.bondResult.dv01, 4)}</span></span>
          </div>
        </div>
      )}

      {mutation.isPending && <Spinner />}

      {scenarios && scenarios.length > 0 && (
        <>
          <div className="card">
            <div className="text-sm font-semibold text-gray-700 mb-4">Price Change by Rate Shock</div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} barSize={36}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="shock" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `${v}%`} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Price Change']}
                />
                <ReferenceLine y={0} stroke="#94a3b8" />
                <Bar dataKey="pct" radius={[3,3,0,0]} fill="#3b82f6" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card overflow-x-auto">
            <div className="text-sm font-semibold text-gray-700 mb-3">Scenario Detail</div>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-400 border-b border-surface-700">
                  <th className="text-left py-2 pr-4">Shock</th>
                  <th className="text-right pr-4">New YTM</th>
                  <th className="text-right pr-4">Price Chg %</th>
                  <th className="text-right pr-4">Dollar Impact</th>
                  <th className="text-right">New Price</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800">
                {scenarios.map(s => (
                  <tr key={s.shock_bps} className="text-gray-600">
                    <td className="py-2 pr-4 font-medium text-gray-700">{s.shock_bps > 0 ? '+' : ''}{s.shock_bps} bps</td>
                    <td className="text-right pr-4">{fmt(s.new_ytm != null ? s.new_ytm * 100 : null, 4)}%</td>
                    <td className={`text-right pr-4 font-semibold ${s.price_change_pct < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                      {s.price_change_pct > 0 ? '+' : ''}{fmt(s.price_change_pct, 2)}%
                    </td>
                    <td className={`text-right pr-4 ${s.dollar_impact < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                      {s.dollar_impact > 0 ? '+' : ''}${fmt(s.dollar_impact, 2)}
                    </td>
                    <td className="text-right font-medium">${fmt(s.new_price, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
