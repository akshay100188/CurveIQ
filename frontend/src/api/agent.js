import { get, post } from './client.js'

export const fetchCurveAnalysis  = ()               => get('/agent/curve-analysis')
export const fetchSysriskAnalysis= ()               => get('/agent/sysrisk-analysis')
export const fetchBondAdvice     = (payload)        => post('/agent/bond-advice', payload)
export const fetchNarratives     = (type, limit=20) => get(`/agent/narratives${type ? `?type=${type}&limit=${limit}` : `?limit=${limit}`}`)
export const fetchAccuracy       = ()               => get('/agent/accuracy')
export const submitFeedback      = (id, is_correct) => post('/agent/feedback', { narrative_id: id, is_correct })
