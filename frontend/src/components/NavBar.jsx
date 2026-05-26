import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, Calculator, Zap,
  AlertTriangle, Clock, MessageSquare,
} from 'lucide-react'

const links = [
  { to: '/dashboard',        label: 'Dashboard',       Icon: LayoutDashboard },
  { to: '/yield-curve',      label: 'Yield Curve',     Icon: TrendingUp       },
  { to: '/bond-calculator',  label: 'Bond Calc',       Icon: Calculator       },
  { to: '/scenario-engine',  label: 'Scenarios',       Icon: Zap              },
  { to: '/credit-stress',    label: 'Credit Stress',   Icon: AlertTriangle    },
  { to: '/crisis-replay',    label: 'Crisis Replay',   Icon: Clock            },
  { to: '/agent-narratives', label: 'AI Analysis',     Icon: MessageSquare    },
]

export default function NavBar() {
  return (
    <aside className="fixed top-0 left-0 h-full w-56 bg-white border-r border-surface-700 flex flex-col z-20 shadow-sm">
      <div className="px-4 py-5 border-b border-surface-700">
        <div className="text-blue-600 font-bold text-lg tracking-tight">CurveIQ</div>
        <div className="text-gray-400 text-xs mt-0.5">Fixed Income Intelligence</div>
      </div>
      <nav className="flex-1 py-3 overflow-y-auto">
        {links.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-600 border border-blue-200'
                  : 'text-gray-500 hover:text-gray-800 hover:bg-surface-800'
              }`
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-3 border-t border-surface-700 text-xs text-gray-400">
        v1.0.0 · US Fixed Income
      </div>
    </aside>
  )
}
