import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export default function StockChart({ data }) {
  if (!data?.length) {
    return <div className="rounded-2xl bg-white p-6 text-slate-500">No chart data available.</div>
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Price Trend</h2>
          <p className="text-sm text-slate-500">Close price with SMA 20 and SMA 50</p>
        </div>
      </div>
      <div className="h-[360px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={28} />
            <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(value) => (value == null ? '-' : `₹${value}`)} />
            <Legend />
            <Line type="monotone" dataKey="close" name="Close" dot={false} strokeWidth={2.2} />
            <Line type="monotone" dataKey="sma20" name="SMA 20" dot={false} strokeWidth={1.6} />
            <Line type="monotone" dataKey="sma50" name="SMA 50" dot={false} strokeWidth={1.6} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
