const rows = [
  ['RSI 14', 'rsi14'],
  ['RSI 5D Change', 'rsi_change_5'],
  ['SMA 20', 'sma20'],
  ['SMA 50', 'sma50'],
  ['MACD', 'macd'],
  ['MACD Signal', 'macd_signal'],
  ['MACD Histogram', 'macd_histogram'],
  ['MACD Hist Slope 3D', 'macd_hist_slope_3'],
  ['+DI 20', 'plus_di_20'],
  ['-DI 20', 'minus_di_20'],
  ['ADX 20', 'adx_20'],
  ['DMI 20 Spread', 'dmi20_spread'],
  ['+DI 50', 'plus_di_50'],
  ['-DI 50', 'minus_di_50'],
  ['ADX 50', 'adx_50'],
  ['DMI 50 Spread', 'dmi50_spread'],
  ['Volume Ratio', 'volume_ratio'],
  ['Volume Ratio 5D', 'volume_ratio_5'],
  ['20-Day Volatility %', 'volatility20'],
  ['ATR 14 %', 'atr14_percent'],
  ['BB Position', 'bb_position'],
  ['Close Position 20D', 'close_position_20'],
  ['Close Position 50D', 'close_position_50'],
  ['Gap Open %', 'gap_open_percent'],
  ['MA20 Gap %', 'ma20_gap_percent'],
  ['MA50 Gap %', 'ma50_gap_percent'],
  ['NIFTY Return 1D %', 'nifty_return_1'],
  ['NIFTY Return 5D %', 'nifty_return_5'],
  ['NIFTY MA20 Gap %', 'nifty_ma20_gap_percent'],
  ['NIFTY ADX 20', 'nifty_adx_20'],
  ['NIFTY DMI 20 Spread', 'nifty_dmi20_spread'],
  ['Bollinger Upper', 'bollinger_upper'],
  ['Bollinger Lower', 'bollinger_lower'],
]

export default function IndicatorTable({ indicators }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-bold text-slate-900">Technical Indicators</h2>
      <p className="mb-4 text-sm text-slate-500">Latest calculated values including trained-model features, SMA, RSI, MACD, DMI-ADX, volume, volatility, and NIFTY context</p>
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
