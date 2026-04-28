import { UserButton } from '@clerk/clerk-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

const NAV: { to: string; label: string }[] = [
  { to: '/', label: 'Dashboard' },
  { to: '/experiments', label: 'Experiments' },
  { to: '/documents', label: 'Documents' },
  { to: '/opportunities', label: 'Opportunities' },
  { to: '/review', label: 'Review' },
  { to: '/directions', label: 'Directions' },
  { to: '/strengthen', label: 'Strengthen' },
  { to: '/state', label: 'Lab state' },
  { to: '/search', label: 'Search' },
  { to: '/literature', label: 'Literature' },
]

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="app">
      <nav className="sidebar" aria-label="Primary">
        <div className="sidebar-top">
          <div className="brand">Phosphor</div>
          <button
            type="button"
            className="ghost menu-toggle"
            aria-expanded={menuOpen}
            aria-controls="primary-nav"
            onClick={() => setMenuOpen((o) => !o)}
          >
            {menuOpen ? 'Close' : 'Menu'}
          </button>
          <div className="sidebar-user">
            <UserButton />
          </div>
        </div>
        <div id="primary-nav" className={`nav-list${menuOpen ? ' open' : ''}`}>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) => `nav${isActive ? ' active' : ''}`}
            >
              {n.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
