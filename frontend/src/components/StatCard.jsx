export default function StatCard({ label, value, sub, accent = 'text-gray-900' }) {
  return (
    <div className="card">
      <div className={`stat-value ${accent}`}>{value ?? '—'}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}
