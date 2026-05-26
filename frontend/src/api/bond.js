import { post } from './client.js'

export const calculateBond    = (payload) => post('/bond/calculate', payload)
export const runScenario      = (payload) => post('/scenario/run',   payload)
