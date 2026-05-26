import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchNarratives, fetchAccuracy, fetchCurveAnalysis, fetchSysriskAnalysis, submitFeedback } from '../api/agent.js'
import Spinner  from '../components/Spinner.jsx'
import ErrorMsg from '../components/ErrorMsg.jsx'
import { ThumbsUp, ThumbsDown, RefreshCw } from 'lucide-react'

const TYPE_LABELS = { curve_analysis: 'Curve Analysis', bond_advice: 'Bond Advice', sysrisk_analysis: 'Systemic Risk' }
const FILTERS = [null, 'curve_analysis', 'sysrisk_analysis', 'bond_advice']
const FILTER_LABELS = { null: 'All', curve_analysis: 'Curve', sysrisk_analysis: 'Sysrisk', bond_advice: 'Bond' }

export default function AgentNarratives() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState(null)
  const [genError, setGenError] = useState(null)

  const narr = useQuery({
    queryKey: ['narratives', filter],
    queryFn: () => fetchNarratives(filter, 20),
  })

  const acc = useQuery({ queryKey: ['accuracy'], queryFn: fetchAccuracy })

  const fbMutation = useMutation({
    mutationFn: ({ id, is_correct }) => submitFeedback(id, is_correct),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['narratives'] }),
  })

  const [generating, setGenerating] = useState(null)
  const generate = async (type) => {
    setGenerating(type)
    setGenError(null)
    try {
      if (type === 'curve_analysis') await fetchCurveAnalysis()
      else if (type === 'sysrisk_analysis') await fetchSysriskAnalysis()
      await qc.invalidateQueries({ queryKey: ['narratives'] })
    } catch (e) {
      setGenError(e.message)
    } finally {
      setGenerating(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">AI Analysis</h1>
          <p className="text-xs text-gray-400 mt-1">Agent-generated narratives · Claude claude-sonnet-4-6 primary · GPT-4o-mini fallback</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => generate('curve_analysis')}   disabled={!!generating}
            className="btn-ghost text-xs flex items-center gap-1.5">
            <RefreshCw size={12} className={generating === 'curve_analysis' ? 'animate-spin' : ''} />
            New Curve Analysis
          </button>
          <button onClick={() => generate('sysrisk_analysis')} disabled={!!generating}
            className="btn-ghost text-xs flex items-center gap-1.5">
            <RefreshCw size={12} className={generating === 'sysrisk_analysis' ? 'animate-spin' : ''} />
            New Sysrisk Analysis
          </button>
        </div>
      </div>

      {genError && <ErrorMsg message={genError} />}

      {/* Accuracy stats */}
      {acc.data && (
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Total Predictions', value: acc.data.total_predictions },
            { label: 'Outcomes Evaluated', value: acc.data.outcomes_evaluated },
            { label: 'Overall Accuracy', value: acc.data.accuracy_pct != null ? `${acc.data.accuracy_pct}%` : '—' },
            { label: 'Pending Evaluation', value: acc.data.total_predictions - acc.data.outcomes_evaluated },
          ].map(s => (
            <div key={s.label} className="card">
              <div className="stat-value">{s.value ?? '—'}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2">
        {FILTERS.map(f => (
          <button key={String(f)} onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${filter === f ? 'bg-blue-600 text-white' : 'btn-ghost'}`}>
            {FILTER_LABELS[f]}
          </button>
        ))}
      </div>

      {/* Narrative list */}
      {narr.isLoading && <Spinner />}
      {narr.isError   && <ErrorMsg message={narr.error?.message} />}

      <div className="space-y-4">
        {narr.data?.map(n => (
          <div key={n.id} className="card space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold text-blue-600">
                  {TYPE_LABELS[n.narrative_type] ?? n.narrative_type}
                </span>
                <span className="text-xs text-gray-400">{n.created_at?.slice(0, 16).replace('T', ' ')}</span>
                {n.model_used && (
                  <span className="text-xs text-gray-500 border border-surface-600 rounded px-1.5 py-0.5">
                    {n.model_used}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {n.user_feedback === true  && <span className="text-xs text-emerald-600">Marked correct</span>}
                {n.user_feedback === false && <span className="text-xs text-red-600">Marked incorrect</span>}
                <button
                  onClick={() => fbMutation.mutate({ id: n.id, is_correct: true })}
                  className={`p-1.5 rounded-lg transition-colors ${n.user_feedback === true ? 'bg-emerald-50 text-emerald-600' : 'hover:bg-surface-800 text-gray-400 hover:text-emerald-600'}`}
                  title="Mark as correct"
                >
                  <ThumbsUp size={13} />
                </button>
                <button
                  onClick={() => fbMutation.mutate({ id: n.id, is_correct: false })}
                  className={`p-1.5 rounded-lg transition-colors ${n.user_feedback === false ? 'bg-red-50 text-red-600' : 'hover:bg-surface-800 text-gray-400 hover:text-red-600'}`}
                  title="Mark as incorrect"
                >
                  <ThumbsDown size={13} />
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {Object.entries(n.narrative || {}).map(([key, val]) => (
                <div key={key}>
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    {key.replace(/_/g, ' ')}
                  </span>
                  <p className="text-sm text-gray-600 leading-relaxed mt-0.5">{String(val)}</p>
                </div>
              ))}
            </div>
            {n.data_snapshot && (
              <details className="text-xs text-gray-400 cursor-pointer">
                <summary className="hover:text-gray-600">Data snapshot</summary>
                <pre className="mt-2 bg-surface-800 rounded p-2 overflow-x-auto text-xs text-gray-600">
                  {JSON.stringify(n.data_snapshot, null, 2)}
                </pre>
              </details>
            )}
          </div>
        ))}
        {narr.data?.length === 0 && (
          <div className="text-center py-12 text-sm text-gray-400">
            No narratives yet. Click "New Curve Analysis" or "New Sysrisk Analysis" to generate one.
          </div>
        )}
      </div>
    </div>
  )
}
