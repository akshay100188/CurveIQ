import { Outlet } from 'react-router-dom'
import NavBar from './NavBar.jsx'

export default function Layout() {
  return (
    <div className="min-h-screen bg-surface-950 flex">
      <NavBar />
      <main className="flex-1 ml-56 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
