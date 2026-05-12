import { useEffect, useState } from 'react'
import {
  Activity,
  AlertCircle,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Gauge,
  RefreshCcw,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { analyzeStock, getDefaultSymbols, getLearningStatus, getModelStatus, runDailyLearningCycle } from './api'
import MetricCard from './components/MetricCard'
import StockChart from './components/StockChart'
import ReasonPanel from './components/ReasonPanel'
import IndicatorTable from './components/IndicatorTable'
import Disclaimer from './components/Disclaimer'

const trendTone = {
  Bullish: 'good',
  Bearish: 'bad',
  Neutral: 'warn',
  Sideways: 'warn',
}

function formatCurrency(value) {
  if (value === null || value === undefined) return '-'
  return `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function formatPercent(value) {
  if (value === null || value === undefined) return '-'
  const sign = Number(value) > 0 ? '+' : ''
  return `${sign}${Number(value).toFixed(2)}%`
}

function TrendIcon({ trend, className = '' }) {
  if (trend === 'Bullish') return <TrendingUp className={`text-emerald-600 ${className}`} />
  if (trend === 'Bearish') return <TrendingDown className={`text-rose-600 ${className}`} />
  return <Gauge className={`text-amber-600 ${className}`} />
}

function SmallStat({ label, value, sub }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-black text-slate-950">{value ?? '-'}</div>
      {sub ? <div className="mt-1 text-xs text-slate-500">{sub}</div> : null}
    </div>
  )
}

function PredictionBox({ title, prediction }) {
  if (!prediction) return null
  const isNeutral = prediction.trend === 'Neutral'
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="rounded-2xl bg-slate-100 p-2">
            <TrendIcon trend={prediction.trend} />
          </div>
          <div>
            <h2 className="text-lg font-black text-slate-950">{title}</h2>
            <p className="text-sm text-slate-500">{prediction.title}</p>
          </div>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-black ${
            prediction.trend === 'Bullish'
              ? 'bg-emerald-100 text-emerald-700'
              : prediction.trend === 'Bearish'
                ? 'bg-rose-100 text-rose-700'
                : 'bg-amber-100 text-amber-700'
          }`}
        >
          {prediction.trend}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <SmallStat label="Up" value={`${prediction.probability_up}%`} />
        <SmallStat label="Neutral" value={`${prediction.probability_neutral}%`} />
        <SmallStat label="Down" value={`${prediction.probability_down}%`} />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <SmallStat label="Confidence" value={`${prediction.confidence}%`} sub={`Filter: ${prediction.confidence_filter_percent}%`} />
        <SmallStat label="Move filter" value={`±${prediction.neutral_threshold_percent}%`} sub="Tiny moves become Neutral" />
      </div>

      <div className={`mt-3 rounded-2xl p-3 text-sm leading-6 ${isNeutral ? 'bg-amber-50 text-amber-900' : 'bg-blue-50 text-blue-900'}`}>
        <b>{isNeutral ? 'Avoid/Neutral reason:' : 'Signal status:'}</b> {prediction.filter_reason}
      </div>
    </div>
  )
}

function BacktestPanel({ prediction }) {
  const bt = prediction?.backtest
  if (!bt) return null
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="text-slate-700" />
        <div>
          <h2 className="text-lg font-black text-slate-950">Backtest Accuracy</h2>
          <p className="text-sm text-slate-500">Holdout result for {prediction.title}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <SmallStat label="All signals" value={bt.accuracy_all_signals !== null ? `${bt.accuracy_all_signals}%` : '-'} />
        <SmallStat label="Confident only" value={bt.accuracy_confident_only !== null ? `${bt.accuracy_confident_only}%` : '-'} />
        <SmallStat label="Coverage" value={bt.confident_signal_coverage !== null ? `${bt.confident_signal_coverage}%` : '-'} />
        <SmallStat label="Test samples" value={bt.test_samples} sub={`${bt.confident_samples || 0} confident`} />
      </div>

      <p className="mt-3 rounded-2xl bg-slate-50 p-3 text-xs leading-5 text-slate-600">
        {bt.note}
      </p>
    </div>
  )
}

function MarketContext({ market }) {
  if (!market) return null
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <Activity className="text-slate-700" />
        <div>
          <h2 className="text-lg font-black text-slate-950">Market Context</h2>
          <p className="text-sm text-slate-500">NIFTY 50 used to adjust confidence</p>
        </div>
      </div>

      {market.available ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            <SmallStat label="NIFTY Trend" value={market.trend} />
            <SmallStat label="Close" value={formatCurrency(market.close)} />
            <SmallStat label="Day Change" value={formatPercent(market.change_percent)} />
            <SmallStat label="RSI 14" value={market.rsi14} />
            <SmallStat label="ADX 20" value={market.adx20} />
            <SmallStat label="DMI Spread" value={market.dmi20_spread} />
          </div>
          <ul className="mt-3 space-y-2">
            {(market.reasons || []).slice(0, 3).map((reason) => (
              <li key={reason} className="rounded-2xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                {reason}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="rounded-2xl bg-amber-50 p-3 text-sm leading-6 text-amber-900">
          {(market.reasons || [])[0] || 'NIFTY 50 context unavailable.'}
        </div>
      )}
    </div>
  )
}


function AutoLearningPanel({ status, running, message, onRun }) {
  const lastRun = status?.last_run
  const recent = status?.recent_predictions || []
  return (
    <div className="rounded-3xl border border-indigo-100 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <BrainCircuit className="text-indigo-600" />
        <div>
          <h2 className="text-lg font-black text-slate-950">Auto Daily Learning</h2>
          <p className="text-sm text-slate-500">Stores predictions, checks actual results, then retrains daily</p>
        </div>
      </div>
      {message ? (
        <div className="mb-3 rounded-2xl bg-indigo-50 p-3 text-sm leading-6 text-indigo-900">
          {message}
        </div>
      ) : null}
      <div className="grid grid-cols-2 gap-2">
        <SmallStat label="Evaluated" value={status?.evaluated_predictions ?? 0} sub="Predictions checked" />
        <SmallStat label="Correct" value={status?.correct_predictions ?? 0} sub={status?.learning_accuracy !== null && status?.learning_accuracy !== undefined ? `${status.learning_accuracy}% learning accuracy` : 'Waiting for actuals'} />
        <SmallStat label="Pending" value={status?.pending_predictions ?? 0} sub="Waiting for future close" />
        <SmallStat label="Total Saved" value={status?.total_predictions ?? 0} sub="Prediction records" />
      </div>
      <button
        onClick={onRun}
        disabled={running}
        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-black text-white shadow-sm transition hover:bg-indigo-500 disabled:opacity-60"
      >
        {running ? <RefreshCcw className="animate-spin" size={16} /> : <BrainCircuit size={16} />}
        {running ? 'Running daily learning...' : 'Run daily learning now'}
      </button>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        The backend also has a scheduler that runs once per IST day after market close when the server is alive. On free hosting, use a cron ping because sleeping servers cannot run background jobs.
      </p>
      {lastRun ? (
        <p className="mt-3 rounded-2xl bg-slate-50 p-3 text-xs leading-5 text-slate-600">
          Last run: <b>{lastRun.run_at}</b> · Processed {lastRun.symbols_processed} symbols · Evaluated {lastRun.predictions_evaluated} predictions · Trained {lastRun.models_trained} models.
        </p>
      ) : null}
      {recent.length ? (
        <div className="mt-3 overflow-hidden rounded-2xl border border-slate-100">
          <div className="grid grid-cols-5 bg-slate-50 px-3 py-2 text-[11px] font-black uppercase text-slate-500">
            <span>Date</span><span>Horizon</span><span>Pred</span><span>Actual</span><span>Status</span>
          </div>
          {recent.slice(0, 5).map((row) => (
            <div key={`${row.id}`} className="grid grid-cols-5 border-t border-slate-100 px-3 py-2 text-xs text-slate-700">
              <span>{row.predicted_on_date}</span>
              <span>{row.horizon_key === 'next_day' ? '1D' : '5D'}</span>
              <span>{row.predicted_trend}</span>
              <span>{row.actual_trend || '-'}</span>
              <span className={row.status === 'evaluated' ? (row.is_correct ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold') : 'text-amber-700 font-bold'}>
                {row.status === 'evaluated' ? (row.is_correct ? 'Correct' : 'Wrong') : 'Pending'}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default function App() {
  const [symbol, setSymbol] = useState('RELIANCE.NS')
  const [symbols, setSymbols] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dailyRunning, setDailyRunning] = useState(false)
  const [learningMessage, setLearningMessage] = useState('')
  const [modelStatus, setModelStatus] = useState(null)
  const [learningStatus, setLearningStatus] = useState(null)

  useEffect(() => {
    getDefaultSymbols()
      .then((res) => setSymbols(res.symbols || []))
      .catch(() => setSymbols([]))
    runAnalysis('RELIANCE.NS')
  }, [])

  async function runAnalysis(customSymbol = symbol) {
    setLoading(true)
    setError('')
    setLearningMessage('')
    try {
      const res = await analyzeStock(customSymbol)
      setData(res)
      setSymbol(res.symbol)
      try {
        const status = await getModelStatus(res.symbol)
        setModelStatus(status)
      } catch {
        setModelStatus(null)
      }
      try {
        const learning = await getLearningStatus(res.symbol)
        setLearningStatus(learning)
      } catch {
        setLearningStatus(res.learning || null)
      }
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  async function runAutoLearningNow() {
    const target = data?.symbol || symbol
    setDailyRunning(true)
    setError('')
    setLearningMessage('Daily learning started. It will check old predictions, retrain models, and save a fresh prediction...')
    try {
      const result = await runDailyLearningCycle(target)
      const status = await getModelStatus(target)
      const learning = await getLearningStatus(target)
      setModelStatus(status)
      setLearningStatus(learning)
      await runAnalysis(target)
      const item = result.symbols?.[target] || result.symbols?.[data?.symbol] || null
      setLearningMessage(
        item
          ? `Daily learning completed: evaluated ${item.evaluated || 0}, trained ${item.trained_models || 0} models, saved ${item.saved_predictions || 0} predictions.`
          : 'Daily learning completed. The model will use the updated saved training package.'
      )
    } catch (err) {
      setError(err.message || 'Daily learning failed')
    } finally {
      setDailyRunning(false)
    }
  }

  const prediction = data?.prediction
  const latest = data?.latest
  const nextDay = prediction?.next_day
  const next5 = prediction?.next_5_day
  const isPositive = Number(latest?.change_percent) >= 0

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 px-4 py-6 text-slate-900 md:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 overflow-hidden rounded-[2rem] border border-slate-200 bg-white/90 p-5 shadow-sm backdrop-blur md:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-black text-white">
                <Sparkles size={14} /> Version 7 · Auto-learning seller demo
              </div>
              <h1 className="text-4xl font-black tracking-tight text-slate-950 md:text-6xl">
                AI NSE Stock Analyzer
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600 md:text-base">
                Bullish, Bearish or Neutral prediction with automatic daily learning, saved symbol-trained ML models, confidence filtering, next trading day view,
                next 5 trading day trend, DMI/ADX trend-strength analysis, backtest accuracy, and NIFTY 50 market context.
              </p>

              <div className="mt-4 flex flex-wrap gap-2 text-xs font-bold text-slate-600">
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">Bullish / Bearish / Neutral</span>
                <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700">Backtest accuracy</span>
                <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">Confidence filter</span>
                <span className="rounded-full bg-purple-50 px-3 py-1 text-purple-700">NIFTY 50 context</span>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-cyan-700">DMI / ADX trend strength</span>
                <span className="rounded-full bg-rose-50 px-3 py-1 text-rose-700">Auto daily learning</span>
              </div>
            </div>

            <div className="w-full rounded-3xl border border-slate-200 bg-slate-50 p-4 lg:max-w-md">
              <div className="mb-2 flex items-center gap-2 text-sm font-bold text-slate-700">
                <Search size={16} /> Search symbol
              </div>
              <div className="flex gap-2">
                <input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && runAnalysis()}
                  placeholder="RELIANCE or RELIANCE.NS"
                  className="min-w-0 flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none ring-blue-200 focus:ring-4"
                />
                <button
                  onClick={() => runAnalysis()}
                  disabled={loading || dailyRunning}
                  className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-black text-white shadow-sm transition hover:bg-slate-700 disabled:opacity-60"
                >
                  {loading ? <RefreshCcw className="animate-spin" size={16} /> : <Search size={16} />}
                  Analyze
                </button>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {symbols.slice(0, 8).map((item) => (
                  <button
                    key={item.symbol}
                    onClick={() => runAnalysis(item.symbol)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 hover:border-slate-900 hover:text-slate-900"
                  >
                    {item.symbol.replace('.NS', '')}
                  </button>
                ))}
              </div>

              <button
                onClick={runAutoLearningNow}
                disabled={dailyRunning || loading}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-black text-white shadow-sm transition hover:bg-indigo-500 disabled:opacity-60"
              >
                {dailyRunning ? <RefreshCcw className="animate-spin" size={16} /> : <BrainCircuit size={16} />}
                {dailyRunning ? 'Running daily learning...' : 'Run auto learning now'}
              </button>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Auto learning checks previous predictions against actual close, retrains saved models, and stores today’s fresh prediction.
              </p>
            </div>
          </div>
        </header>

        {error ? (
          <div className="mb-5 flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800">
            <AlertCircle className="mt-0.5" size={18} />
            <div>
              <div className="font-bold">Could not load analysis</div>
              <div className="text-sm">{error}</div>
            </div>
          </div>
        ) : null}

        {loading && !data ? (
          <div className="rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm">
            <RefreshCcw className="mx-auto mb-4 animate-spin text-slate-700" size={30} />
            <div className="text-lg font-bold">Fetching data and running Version 7 auto-learning analysis...</div>
            <div className="text-sm text-slate-500">This can take a few seconds for the first request.</div>
          </div>
        ) : null}

        {data ? (
          <div className="space-y-5">
            <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
              <MetricCard label="Symbol" value={data.symbol} subValue={latest?.date} tone="info" />
              <MetricCard label="Latest Close" value={formatCurrency(latest?.close)} subValue="latest available price" />
              <MetricCard
                label="Day Change"
                value={formatPercent(latest?.change_percent)}
                subValue={formatCurrency(latest?.change)}
                tone={isPositive ? 'good' : 'bad'}
              />
              <MetricCard
                label="Next Trading Day"
                value={nextDay?.trend}
                subValue={`${nextDay?.confidence}% confidence`}
                tone={trendTone[nextDay?.trend] || 'default'}
              />
              <MetricCard
                label="Next 5 Trading Days"
                value={next5?.trend}
                subValue={`${next5?.confidence}% confidence`}
                tone={trendTone[next5?.trend] || 'default'}
              />
              <MetricCard
                label="Risk Level"
                value={prediction?.risk_level}
                subValue={`${prediction?.risk_score}/100 risk score`}
                tone={prediction?.risk_level === 'High' ? 'bad' : prediction?.risk_level === 'Medium' ? 'warn' : 'good'}
              />
            </section>

            <section className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <PredictionBox title="Next Trading Day Prediction" prediction={nextDay} />
              <PredictionBox title="Next 5 Trading Day Prediction" prediction={next5} />
            </section>

            <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1.25fr_0.75fr]">
              <StockChart data={data.chart} />
              <div className="space-y-5">
                <MarketContext market={data.market_context} />
                <AutoLearningPanel status={learningStatus || data.learning} message={learningMessage} running={dailyRunning} onRun={runAutoLearningNow} />
                <BacktestPanel prediction={nextDay} />
              </div>
            </section>

            <section className="grid grid-cols-1 gap-5 xl:grid-cols-[0.8fr_1fr]">
              <BacktestPanel prediction={next5} />
              <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <CheckCircle2 className="text-emerald-600" />
                  <div>
                    <h2 className="text-lg font-black text-slate-950">Seller Demo Notes</h2>
                    <p className="text-sm text-slate-500">How to explain this version</p>
                  </div>
                </div>
                <div className="space-y-3 text-sm leading-6 text-slate-700">
                  <p className="rounded-2xl bg-slate-50 p-3">
                    This version does not force a prediction every time. If confidence is weak, it gives <b>Neutral/Avoid</b>.
                  </p>
                  <p className="rounded-2xl bg-slate-50 p-3">
                    Accuracy shown here is a demo holdout backtest from historical data, not a guaranteed future result. DMI/ADX helps reduce weak-trend false signals but cannot guarantee profit.
                  </p>
                  <p className="rounded-2xl bg-slate-50 p-3">
                    Free automatic public market data is used for demo. Official NSE/vendor feed can be connected later.
                  </p>
                </div>
              </div>
            </section>

            <section className="grid grid-cols-1 gap-5 xl:grid-cols-[0.7fr_1fr]">
              <IndicatorTable indicators={data.indicators} />
              <ReasonPanel reasons={data.reasons} summary={data.summary} />
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-3 flex items-center gap-2">
                <ShieldCheck className="text-slate-700" />
                <h2 className="text-lg font-black text-slate-950">Data Mode</h2>
              </div>
              <p className="text-sm leading-6 text-slate-600">{data.data_source_note}</p>
            </section>

            <Disclaimer />
          </div>
        ) : null}
      </div>
    </main>
  )
}
