import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import YieldCurve from './pages/YieldCurve.jsx'
import BondCalculator from './pages/BondCalculator.jsx'
import ScenarioEngine from './pages/ScenarioEngine.jsx'
import CreditStress from './pages/CreditStress.jsx'
import CrisisReplay from './pages/CrisisReplay.jsx'
import AgentNarratives from './pages/AgentNarratives.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="yield-curve" element={<YieldCurve />} />
          <Route path="bond-calculator" element={<BondCalculator />} />
          <Route path="scenario-engine" element={<ScenarioEngine />} />
          <Route path="credit-stress" element={<CreditStress />} />
          <Route path="crisis-replay" element={<CrisisReplay />} />
          <Route path="agent-narratives" element={<AgentNarratives />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
