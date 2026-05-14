const groups = [
  {
    title: 'Price Momentum',
    rows: [
      ['Current momentum score', 'rsi14'],
      ['Recent momentum change', 'rsi_change_5'],
      ['Short average position', 'sma20'],
      ['Long average position', 'sma50'],
      ['20-day price position', 'close_position_20'],
      ['50-day price position', 'close_position_50'],
    ],
  },
  {
    title: 'Trend Direction',
    rows: [
      ['Short trend gap', 'ma20_gap_percent'],
      ['Long trend gap', 'ma50_gap_percent'],
      ['Main trend signal', 'macd'],
      ['Trend confirmation line', 'macd_signal'],
      ['Trend pressure difference', 'macd_histogram'],
      ['Recent trend pressure change', 'macd_hist_slope_3'],
    ],
  },
  {
    title: 'Trend Strength',
    rows: [
      ['Short positive strength', 'plus_di_20'],
      ['Short negative strength', 'minus_di_20'],
      ['Short trend strength', 'adx_20'],
      ['Short direction balance', 'dmi20_spread'],
      ['Long positive strength', 'plus_di_50'],
      ['Long negative strength', 'minus_di_50'],
      ['Long trend strength', 'adx_50'],
      ['Long direction balance', 'dmi50_spread'],
    ],
  },
  {
    title: 'Activity and Risk',
    rows: [
      ['Buying/Selling activity', 'volume_ratio'],
      ['Recent activity level', 'volume_ratio_5'],
      ['20-day risk movement', 'volatility20'],
      ['Average daily movement risk', 'atr14_percent'],
      ['Opening gap movement', 'gap_open_percent'],
    ],
  },
  {
    title: 'Price Range',
    rows: [
      ['Price range position', 'bb_position'],
      ['Upper range level', 'bollinger_upper'],
      ['Lower range level', 'bollinger_lower'],
    ],
  },
  {
    title: 'Overall Market Support',
    rows: [
      ['Market 1-day support', 'nifty_return_1'],
      ['Market 5-day support', 'nifty_return_5'],
      ['Market average gap', 'nifty_ma20_gap_percent'],
      ['Market trend strength', 'nifty_adx_20'],
      ['Market direction balance', 'nifty_dmi20_spread'],
    ],
  },
]

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  return value
}

export default function IndicatorTable({ indicators }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-bold text-slate-900">Analysis Factors</h2>
      <p className="mb-4 text-sm leading-6 text-slate-500">
        These are the main market signals considered by the system. They are shown in simple language so a normal user can understand the reason behind the result.
      </p>

      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.title} className="overflow-hidden rounded-xl border border-slate-100">
            <div className="bg-slate-900 px-4 py-2 text-sm font-bold text-white">{group.title}</div>
            <table className="w-full border-collapse text-sm">
              <tbody>
                {group.rows.map(([label, key], i) => (
                  <tr key={key} className={i % 2 === 0 ? 'bg-slate-50' : 'bg-white'}>
                    <td className="px-4 py-3 font-medium text-slate-600">{label}</td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-900">
                      {formatValue(indicators?.[key])}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  )
}
