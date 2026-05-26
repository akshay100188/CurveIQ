import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCrisisPeriods, fetchCreditRange } from '../api/credit.js'
import { fetchSpreadRange } from '../api/curve.js'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend } from 'recharts'
import Spinner  from '../components/Spinner.jsx'
import ErrorMsg from '../components/ErrorMsg.jsx'

export default function CrisisReplay() {
  const [selected, setSelected] = useState(null)

  const periods = useQuery({ queryKey: ['crisis-periods'], queryFn: fetchCrisisPeriods })

  const credit = useQuery({
    queryKey: ['credit-history-crisis', selected?.name],
    queryFn: () => fetchCreditRange(selected.start_date, selected.end_date),
    enabled: !!selected,
  })

  const spread = useQuery({
    queryKey: ['spread-history-crisis', selected?.name],
    queryFn: () => fetchSpreadRange(selected.start_date, selected.end_date),
    enabled: !!selected,
  })

  if (periods.isLoading) return <Spinner />
  if (periods.isError)   return <ErrorMsg message={periods.error?.message} />

  const creditData = (credit.data || []).map(r => ({
    date:  r.date?.slice(0, 7),
    score: r.stress_score != null ? Number(r.stress_score) : null,
    hy:    r.hy_oas        != null ? Number(r.hy_oas)       : null,
    vix:   r.vix           != null ? Number(r.vix)          : null,
  }))

  const spreadData = (spread.data || []).map(r => ({
    date: r.date?.slice(0, 7),
    '2Y–10Y': r.spread_2y10y != null ? Number(r.spread_2y10y) : null,
  }))

  const peakStress = creditData.reduce((mx, r) => (r.score > (mx?.score ?? -1) ? r : mx), null)
  const peakVix    = creditData.reduce((mx, r) => (r.vix   > (mx?.vix   ?? -1) ? r : mx), null)
  const peakHy     = creditData.reduce((mx, r) => (r.hy    > (mx?.hy    ?? -1) ? r : mx), null)
  const minSpread  = spreadData.reduce((mn, r) => ((r['2Y–10Y'] ?? 99) < (mn?.['2Y–10Y'] ?? 99) ? r : mn), null)

  const tooltipStyle = { background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.07)' }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Crisis Replay</h1>
        <p className="text-xs text-gray-400 mt-1">Visualise market stress during historical crisis periods</p>
      </div>

      {/* Crisis selector */}
      <div className="grid grid-cols-3 gap-4">
        {periods.data?.map(p => (
          <button
            key={p.name}
            onClick={() => setSelected(p)}
            className={`card text-left transition-all hover:border-blue-300 hover:shadow-md ${selected?.name === p.name ? 'border-blue-400 bg-blue-50' : ''}`}
          >
            <div className="text-sm font-semibold text-gray-800">{p.name}</div>
            <div className="text-xs text-gray-400 mt-1">{p.start_date} → {p.end_date}</div>
            <div className="text-xs text-gray-500 mt-2 line-clamp-2">{p.description}</div>
          </button>
        ))}
      </div>

      {selected && (
        <>
          {(credit.isLoading || spread.isLoading) && <Spinner />}

          {/* Peak stats */}
          {creditData.length > 0 && (
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: 'Peak Stress Score', value: peakStress?.score?.toFixed(1), sub: peakStress?.date, accent: 'text-red-600' },
                { label: 'Peak VIX',          value: peakVix?.vix?.toFixed(1),     sub: peakVix?.date    },
                { label: 'Peak HY OAS',       value: peakHy?.hy != null ? `${peakHy.hy.toFixed(2)}%` : '—', sub: peakHy?.date },
                { label: 'Min 2Y–10Y Spread', value: minSpread?.['2Y–10Y'] != null ? `${minSpread['2Y–10Y'].toFixed(2)}%` : '—', sub: minSpread?.date, accent: 'text-amber-600' },
              ].map(item => (
                <div key={item.label} className="card">
                  <div className={`text-2xl font-bold ${item.accent ?? 'text-gray-900'}`}>{item.value ?? '—'}</div>
                  <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">{item.label}</div>
                  {item.sub && <div className="text-xs text-gray-400 mt-1">{item.sub}</div>}
                </div>
              ))}
            </div>
          )}

          {/* Stress + VIX over crisis */}
          {creditData.length > 0 && (
            <div className="card">
              <div className="text-sm font-semibold text-gray-700 mb-4">
                Stress Score &amp; VIX — {selected.name}
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={creditData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis yAxisId="l" tick={{ fill: '#64748b', fontSize: 10 }} domain={[0, 100]} />
                  <YAxis yAxisId="r" orientation="right" tick={{ fill: '#64748b', fontSize: 10 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#64748b' }} />
                  <Line yAxisId="l" dataKey="score" stroke="#dc2626" dot={false} strokeWidth={2} name="Stress Score" connectNulls />
                  <Line yAxisId="r" dataKey="vix"   stroke="#d97706" dot={false} strokeWidth={1.5} name="VIX" connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Spread over crisis */}
          {spreadData.length > 0 && (
            <div className="card">
              <div className="text-sm font-semibold text-gray-700 mb-4">
                2Y–10Y Spread — {selected.name}
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={spreadData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `${v}%`} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="4 4" />
                  <Line dataKey="2Y–10Y" stroke="#3b82f6" dot={false} strokeWidth={2} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {creditData.length === 0 && !credit.isLoading && (
            <div className="card text-xs text-gray-400 text-center py-8">
              No data available for this crisis period in the database.
            </div>
          )}
        </>
      )}
    </div>
  )
}
