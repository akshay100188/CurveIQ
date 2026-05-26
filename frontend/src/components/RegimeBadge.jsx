export default function RegimeBadge({ regime }) {
  if (!regime) return null
  const cls = {
    calm:   'badge-calm',
    watch:  'badge-watch',
    stress: 'badge-stress',
    crisis: 'badge-crisis',
  }[regime.toLowerCase()] ?? 'badge-watch'
  return <span className={cls}>{regime.toUpperCase()}</span>
}
