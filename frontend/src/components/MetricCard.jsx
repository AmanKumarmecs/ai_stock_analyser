export default function MetricCard({ label, value, subValue, tone = 'default' }) {
  const toneClass = {
    default: 'bg-white/80 border-slate-200',
    good: 'bg-emerald-50 border-emerald-200',
    bad: 'bg-rose-50 border-rose-200',
    warn: 'bg-amber-50 border-amber-200',
    info: 'bg-blue-50 border-blue-200',
  }[tone]

  return (
    <div className={`rounded-2xl border p-4 shadow-sm ${toneClass}`}>
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-slate-900">{value ?? '-'}</div>
      {subValue ? <div className="mt-1 text-xs text-slate-500">{subValue}</div> : null}
    </div>
  )
}
