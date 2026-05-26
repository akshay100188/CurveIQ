import { get } from './client.js'

export const fetchCurveLatest      = ()           => get('/curve/latest')
export const fetchCurveHistory     = (days = 90)  => get(`/curve/history?days=${days}`)
export const fetchSpreadHistory    = (days = 365) => get(`/curve/spreads?days=${days}`)
export const fetchSpreadRange      = (start, end) => get(`/curve/spreads?start_date=${start}&end_date=${end}`)
export const fetchFedDecisions     = (limit = 20) => get(`/curve/fed-decisions?limit=${limit}`)
