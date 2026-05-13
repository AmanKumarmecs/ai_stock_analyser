import { BrainCircuit } from 'lucide-react'
import { cleanPublicText } from '../publicText'

export default function ReasonPanel({ reasons = [], summary }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <div className="rounded-xl bg-slate-900 p-2 text-white">
          <BrainCircuit size={18} />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">Why this result is shown</h2>
          <p className="text-sm text-slate-500">Simple explanation for the user</p>
        </div>
      </div>

      {summary ? (
        <div className="mb-4 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">
          {cleanPublicText(summary)}
        </div>
      ) : null}

      <ul className="space-y-2">
        {reasons.map((reason, index) => (
          <li key={reason} className="flex gap-3 rounded-xl border border-slate-100 p-3 text-sm text-slate-700">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
              {index + 1}
            </span>
            <span>{cleanPublicText(reason)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
