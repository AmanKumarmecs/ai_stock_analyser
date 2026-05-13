const rows = [
  ['Momentum score', 'rsi14'],
  ['Short-term trend level', 'ma20_gap_percent'],
  ['Medium-term trend level', 'ma50_gap_percent'],
  ['Market support', 'nifty_return_1'],
  ['5-day market support', 'nifty_return_5'],
  ['Buying/Selling activity', 'volume_ratio'],
  ['Recent activity level', 'volume_ratio_5'],
  ['Risk movement level', 'volatility20'],
  ['Price strength position', 'close_position_20'],
  ['Price range position', 'bb_position'],
]

export default function IndicatorTable({ indicators }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-bold text-slate-900">Analysis Factors</h2>
      <p className="mb-4 text-sm text-slate-500">Main market factors used to prepare the result, shown in simple language.</p>
      <div className="overflow-hidden rounded-xl border border-slate-100">
        <table className="w-full border-collapse text-sm">
          <tbody>
            {rows.map(([label, key], i) => (
              <tr key={key} className={i % 2 === 0 ? 'bg-slate-50' : 'bg-white'}>
                <td className="px-4 py-3 font-medium text-slate-600">{label}</td>
                <td className="px-4 py-3 text-right font-semibold text-slate-900">
                  {indicators?.[key] ?? '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
