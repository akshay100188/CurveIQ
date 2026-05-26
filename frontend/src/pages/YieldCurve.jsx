import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCurveLatest, fetchSpreadHistory, fetchFedDecisions } from '../api/curve.js'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import Spinner     from '../components/Spinner.jsx'
import ErrorMsg    from '../components/ErrorMsg.jsx'
import RegimeBadge from '../components/RegimeBadge.jsx'

const TENORS = ['t3m','t6m','t1y','t2y','t3y','t5y','t7y','t10y','t20y','t30y']
const TENOR_LABELS = { t3m:'3M', t6m:'6M', t1y:'1Y', t2y:'2Y', t3y:'3Y', t5y:'5Y', t7y:'7Y', t10y:'10Y', t20y:'20Y', t30y:'30Y' }

const DAYS_OPTIONS = [90, 180, 365, 730]

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 text-xs space-y-1 shadow-md">
      <div className="text-gray-500 mb-1">{label}</div>
      {payload.map(p => (
        <div key={p.name} className="flex gap-2 justify-between">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="text-gray-800 font-medium">{Number(p.value).toFixed(2)}%</span>
        </div>
      ))}
    </div>
  )
}

export default function YieldCurve() {
  const [days, setDays] = useState(365)

  const latest = useQuery({ queryKey: ['curve-latest'],          queryFn: fetchCurveLatest })
  const spread = useQuery({ queryKey: ['spread-history', days],  queryFn: () => fetchSpreadHistory(days) })
  const fed    = useQuery({ queryKey: ['fed-decisions'],         queryFn: () => fetchFedDecisions(30) })

  if (latest.isLoading) return <Spinner />
  if (latest.isError)   return <ErrorMsg message={latest.error?.message} />

  const c = latest.data || {}

  const snapshotData = TENORS
    .filter(k => c[k] != null)
    .map(k => ({ tenor: TENOR_LABELS[k], yield: Number(c[k]) }))

  const spreadData = (spread.data || []).map(row => ({
    date: row.date?.slice(0,7),
    '2Y–10Y': row.spread_2y10y != null ? Number(row.spread_2y10y) : null,
    '3M–10Y': row.spread_3m10y != null ? Number(row.spread_3m10y) : null,
  }))

  const fedData = (fed.data || []).filter(d => d.decision_type !== 'future').slice(-20)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Yield Curve</h1>
          <p className="text-xs text-gray-400 mt-1">Latest: {c.date ?? '—'} · Shape: <span className="text-gray-700">{c.curve_shape ?? '—'}</span></p>
        </div>
        <div className="flex gap-2">
          {DAYS_OPTIONS.map(d => (
            <button key={d} onClick={() => setDays(d)}
              className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${days === d ? 'bg-blue-600 text-white' : 'btn-ghost'}`}>
              {d === 730 ? '2Y' : d === 365 ? '1Y' : d === 180 ? '6M' : '3M'}
            </button>
          ))}
        </div>
      </div>

      {/* Current snapshot */}
      <div className="card">
        <div className="text-sm font-semibold text-gray-700 mb-4">Current Yield Curve</div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={snapshotData} barSize={28}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="tenor" tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `${v}%`} domain={['auto', 'auto']} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="yield" fill="#3b82f6" radius={[3,3,0,0]} />
          </BarChart>
        </ResponsiveContainer>
        <div className="flex gap-6 mt-3 text-xs text-gray-500">
          <span>2Y: <span className="text-gray-800 font-medium">{Number(c.t2y).toFixed(2)}%</span></span>
          <span>10Y: <span className="text-gray-800 font-medium">{Number(c.t10y).toFixed(2)}%</span></span>
          <span>Spread 2Y–10Y: <span className={c.spread_2y10y < 0 ? 'text-red-600' : 'text-emerald-600'}>{Number(c.spread_2y10y).toFixed(2)}%</span></span>
          <span>3M–10Y: <span className={c.spread_3m10y < 0 ? 'text-red-600' : 'text-emerald-600'}>{Number(c.spread_3m10y).toFixed(2)}%</span></span>
        </div>
      </div>

      {/* Spread history */}
      <div className="card">
        <div className="text-sm font-semibold text-gray-700 mb-4">Spread History</div>
        {spread.isLoading ? <Spinner /> : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={spreadData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `${v}%`} />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="4 4" />
              <Legend wrapperStyle={{ fontSize: 11, color: '#64748b' }} />
              <Line dataKey="2Y–10Y" stroke="#3b82f6" dot={false} strokeWidth={1.5} connectNulls />
              <Line dataKey="3M–10Y" stroke="#f59e0b" dot={false} strokeWidth={1.5} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Fed decisions */}
      <div className="card">
        <div className="text-sm font-semibold text-gray-700 mb-3">Recent Fed Decisions</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-surface-700">
                <th className="text-left py-2 pr-4">Date</th>
                <th className="text-right pr-4">Before</th>
                <th className="text-right pr-4">After</th>
                <th className="text-right pr-4">Change</th>
                <th className="text-left">Decision</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-800">
              {fedData.map(d => (
                <tr key={d.id} className="text-gray-600">
                  <td className="py-2 pr-4 text-gray-500">{d.decision_date}</td>
                  <td className="text-right pr-4">{d.rate_before != null ? `${Number(d.rate_before).toFixed(2)}%` : '—'}</td>
                  <td className="text-right pr-4">{d.rate_after  != null ? `${Number(d.rate_after).toFixed(2)}%`  : '—'}</td>
                  <td className={`text-right pr-4 font-medium ${d.rate_change > 0 ? 'text-red-600' : d.rate_change < 0 ? 'text-emerald-600' : 'text-gray-400'}`}>
                    {d.rate_change != null ? `${d.rate_change > 0 ? '+' : ''}${Number(d.rate_change).toFixed(2)}%` : '—'}
                  </td>
                  <td>
                    <span className={`capitalize font-medium ${d.decision_type === 'hike' ? 'text-red-600' : d.decision_type === 'cut' ? 'text-emerald-600' : 'text-gray-400'}`}>
                      {d.decision_type}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
