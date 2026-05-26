import { get } from './client.js'

export const fetchCreditLatest   = ()            => get('/credit/latest')
export const fetchCreditHistory  = (days = 365)  => get(`/credit/history?days=${days}`)
export const fetchCreditRange    = (start, end)  => get(`/credit/history?start_date=${start}&end_date=${end}`)
export const fetchStressScore    = ()            => get('/credit/stress-score')
export const fetchCrisisPeriods  = ()            => get('/credit/crisis-periods')
