import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchStressScore, fetchCreditHistory } from '../api/credit.js'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import Spinner     from '../components/Spinner.jsx'
import ErrorMsg    from '../components/ErrorMsg.jsx'
import RegimeBadge from '../components/RegimeBadge.jsx'

const DAYS_OPTIONS = [90, 365, 730, 3650]
const DAY_LABEL = { 90: '3M', 365: '1Y', 730: '2Y', 3650: '10Y' }

function GaugeArc({ score }) {
  const pct = Math.min(Math.max(score || 0, 0), 100)
  const color = pct > 75 ? '#dc2626' : pct > 50 ? '#ea580c' : pct > 25 ? '#d97706' : '#16a34a'
  const r = 64, cx = 80, cy = 80
  const startAngle = 200, sweep = 140
  const toRad = d => (d * Math.PI) / 180
  const startR = toRad(startAngle)
  const endR   = toRad(startAngle + sweep * (pct / 100))
  const x1 = cx + r * Math.cos(startR), y1 = cy + r * Math.sin(startR)
  const x2 = cx + r * Math.cos(endR),   y2 = cy + r * Math.sin(endR)
  const largeArc = sweep * (pct / 100) > 180 ? 1 : 0

  const bgEnd = toRad(startAngle + sweep)
  const bx = cx + r * Math.cos(bgEnd), by = cy + r * Math.sin(bgEnd)

  return (
    <svg viewBox="0 0 160 120" className="w-40 h-32">
      <path d={`M ${x1} ${y1} A ${r} ${r} 0 1 1 ${bx} ${by}`} fill="none" stroke="#e2e8f0" strokeWidth={10} strokeLinecap="round" />
      {pct > 0 && (
        <path d={`M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`} fill="none" stroke={color} strokeWidth={10} strokeLinecap="round" />
      )}
      <text x={cx} y={cy + 8} textAnchor="middle" fill={color} fontSize={22} fontWeight="700" fontFamily="monospace">{Math.round(pct)}</text>
      <text x={cx} y={cy + 22} textAnchor="middle" fill="#94a3b8" fontSize={9}>/ 100</text>
    </svg>
  )
}

const COMPONENT_LABELS = { hy_oas: 'HY OAS', ig_oas: 'IG OAS', ted_spread: 'TED Spread', vix: 'VIX', spread_2y10y: '2Y–10Y Spread' }

export default function CreditStress() {
  const [days, setDays] = useState(365)

  const score   = useQuery({ queryKey: ['stress-score'],          queryFn: fetchStressScore })
  const history = useQuery({ queryKey: ['credit-history', days],  queryFn: () => fetchCreditHistory(days) })

  if (score.isLoading) return <Spinner />
  if (score.isError)   return <ErrorMsg message={score.error?.message} />

  const s  = score.data || {}
  const cs = s.component_scores || {}

  const compData = Object.entries(COMPONENT_LABELS).map(([k, label]) => ({
    name: label, score: cs[k] != null ? Math.round(Number(cs[k])) : null,
  })).filter(d => d.score != null)

  const histData = (history.data || []).map(row => ({
    date:  row.date?.slice(0, 7),
    score: row.stress_score != null ? Number(row.stress_score) : null,
    hy:    row.hy_oas       != null ? Number(row.hy_oas)       : null,
    vix:   row.vix          != null ? Number(row.vix)          : null,
  }))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Credit Stress</h1>
          <p className="text-xs text-gray-400 mt-1">As of {s.date ?? '—'}</p>
        </div>
        <div className="flex gap-2">
          {DAYS_OPTIONS.map(d => (
            <button key={d} onClick={() => setDays(d)}
              className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${days === d ? 'bg-blue-600 text-white' : 'btn-ghost'}`}>
              {DAY_LABEL[d]}
            </button>
          ))}
        </div>
      </div>

      {/* Score + components */}
      <div className="grid grid-cols-2 gap-6">
        <div className="card flex flex-col items-center justify-center gap-2">
          <GaugeArc score={s.stress_score} />
          <RegimeBadge regime={s.stress_regime} />
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 mt-3 text-xs w-full">
            {[
              ['HY OAS',    s.hy_oas,     '%'],
              ['IG OAS',    s.ig_oas,     '%'],
              ['VIX',       s.vix,        ''],
              ['TED Spread',s.ted_spread, '%'],
            ].map(([l, v, u]) => (
              <div key={l} className="flex justify-between">
                <span className="text-gray-400">{l}</span>
                <span className="text-gray-800 font-medium">{v != null ? `${Number(v).toFixed(2)}${u}` : '—'}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="text-sm font-semibold text-gray-700 mb-4">Component Scores</div>
          {compData.length === 0 && <p className="text-xs text-gray-400">No component scores available.</p>}
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={compData} layout="vertical" barSize={14}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis dataKey="name" type="category" width={90} tick={{ fill: '#64748b', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.07)' }}
                formatter={v => [`${v}`, 'Score']}
              />
              <ReferenceLine x={75} stroke="#dc262640" strokeDasharray="3 3" />
              <ReferenceLine x={50} stroke="#ea580c40" strokeDasharray="3 3" />
              <ReferenceLine x={25} stroke="#d9770640" strokeDasharray="3 3" />
              <Bar dataKey="score" fill="#3b82f6" radius={[0,3,3,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Stress history */}
      <div className="card">
        <div className="text-sm font-semibold text-gray-700 mb-4">Stress Score History</div>
        {history.isLoading ? <Spinner /> : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={histData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} domain={[0, 100]} />
              <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.07)' }} />
              <ReferenceLine y={75} stroke="#dc262640" strokeDasharray="3 3" label={{ value: 'Crisis', fill: '#dc2626', fontSize: 10, position: 'right' }} />
              <ReferenceLine y={50} stroke="#ea580c40" strokeDasharray="3 3" label={{ value: 'Stress', fill: '#ea580c', fontSize: 10, position: 'right' }} />
              <ReferenceLine y={25} stroke="#d9770640" strokeDasharray="3 3" label={{ value: 'Watch',  fill: '#d97706', fontSize: 10, position: 'right' }} />
              <Line dataKey="score" stroke="#3b82f6" dot={false} strokeWidth={1.5} connectNulls name="Stress Score" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
