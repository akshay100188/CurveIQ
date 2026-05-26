import { useQuery } from '@tanstack/react-query'
import { fetchCurveLatest } from '../api/curve.js'
import { fetchStressScore } from '../api/credit.js'
import { fetchNarratives  } from '../api/agent.js'
import StatCard    from '../components/StatCard.jsx'
import RegimeBadge from '../components/RegimeBadge.jsx'
import Spinner     from '../components/Spinner.jsx'
import ErrorMsg    from '../components/ErrorMsg.jsx'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

function shapeColor(shape) {
  return { normal: 'text-emerald-600', inverted: 'text-red-600', flat: 'text-amber-600', humped: 'text-blue-600' }[shape] ?? 'text-gray-700'
}

function fmt(v, d = 2) {
  return v != null ? Number(v).toFixed(d) : '—'
}

export default function Dashboard() {
  const curve   = useQuery({ queryKey: ['curve-latest'],   queryFn: fetchCurveLatest })
  const stress  = useQuery({ queryKey: ['stress-score'],   queryFn: fetchStressScore })
  const narr    = useQuery({ queryKey: ['narratives', 'all', 3], queryFn: () => fetchNarratives(null, 3) })

  if (curve.isLoading || stress.isLoading) return <Spinner />
  if (curve.isError)  return <ErrorMsg message={curve.error?.message} />

  const c = curve.data  || {}
  const s = stress.data || {}

  const tenors = [
    { label: '3M', value: c.t3m }, { label: '6M', value: c.t6m },
    { label: '1Y', value: c.t1y }, { label: '2Y', value: c.t2y },
    { label: '3Y', value: c.t3y }, { label: '5Y', value: c.t5y },
    { label: '7Y', value: c.t7y }, { label: '10Y', value: c.t10y },
    { label: '20Y', value: c.t20y },{ label: '30Y', value: c.t30y },
  ].filter(t => t.value != null)

  const radarData = tenors.map(t => ({ tenor: t.label, yield: Number(t.value) }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-xs text-gray-400 mt-1">US Fixed Income Intelligence · {c.date ?? '—'}</p>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Curve Shape"
          value={c.curve_shape ?? '—'}
          accent={shapeColor(c.curve_shape)}
          sub={`2Y–10Y spread: ${fmt(c.spread_2y10y)}%`}
        />
        <StatCard label="10Y Yield" value={`${fmt(c.t10y)}%`} sub={`2Y: ${fmt(c.t2y)}%`} />
        <StatCard
          label="Stress Score"
          value={fmt(s.stress_score, 1)}
          accent={s.stress_score > 75 ? 'text-red-600' : s.stress_score > 50 ? 'text-orange-500' : s.stress_score > 25 ? 'text-amber-500' : 'text-emerald-600'}
          sub={<RegimeBadge regime={s.stress_regime} />}
        />
        <StatCard label="VIX" value={fmt(s.vix, 1)} sub={`HY OAS: ${fmt(s.hy_oas, 2)}%`} />
      </div>

      {/* Yield curve snapshot + narratives */}
      <div className="grid grid-cols-2 gap-6">
        <div className="card">
          <div className="text-sm font-semibold text-gray-700 mb-3">Yield Curve Snapshot</div>
          <ResponsiveContainer width="100%" height={200}>
            <RadarChart data={radarData} cx="50%" cy="50%">
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="tenor" tick={{ fill: '#64748b', fontSize: 11 }} />
              <Radar dataKey="yield" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.12} strokeWidth={2} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.07)' }}
                labelStyle={{ color: '#374151' }}
                formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Yield']}
              />
            </RadarChart>
          </ResponsiveContainer>
          <div className="mt-2 text-right">
            <Link to="/yield-curve" className="text-xs text-blue-600 hover:text-blue-700 inline-flex items-center gap-1">
              Full analysis <ArrowRight size={12} />
            </Link>
          </div>
        </div>

        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-gray-700">Recent AI Narratives</div>
            <Link to="/agent-narratives" className="text-xs text-blue-600 hover:text-blue-700 inline-flex items-center gap-1">
              All <ArrowRight size={12} />
            </Link>
          </div>
          {narr.isLoading && <Spinner />}
          {narr.data?.length === 0 && (
            <p className="text-xs text-gray-400">No narratives yet. Go to AI Analysis to generate one.</p>
          )}
          {narr.data?.map(n => (
            <div key={n.id} className="border-l-2 border-blue-200 pl-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-gray-500 capitalize">{n.narrative_type?.replace(/_/g,' ')}</span>
                <span className="text-xs text-gray-400">{n.created_at?.slice(0,10)}</span>
              </div>
              <p className="text-xs text-gray-600 line-clamp-2">
                {n.narrative?.stress_summary ?? n.narrative?.curve_shape_summary ?? Object.values(n.narrative || {})[1] ?? ''}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Quick-action row */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { to: '/bond-calculator',  label: 'Bond Calculator', desc: 'Price bonds, compute duration & DV01' },
          { to: '/credit-stress',    label: 'Credit Stress',   desc: 'Live stress score & component breakdown' },
          { to: '/crisis-replay',    label: 'Crisis Replay',   desc: 'Replay 2008, 2020 & 2011 market stress' },
        ].map(item => (
          <Link key={item.to} to={item.to} className="card hover:border-blue-300 hover:shadow-md transition-all group">
            <div className="text-sm font-semibold text-gray-800 group-hover:text-blue-600 transition-colors">{item.label}</div>
            <div className="text-xs text-gray-400 mt-1">{item.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
