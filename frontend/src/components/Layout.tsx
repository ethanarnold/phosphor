import { OrganizationSwitcher, UserButton } from '@clerk/clerk-react'
import { NavLink, Outlet } from 'react-router-dom'
import BrandMark from './BrandMark'

const NAV: { to: string; label: string }[] = [
  { to: '/', label: 'Dashboard' },
  { to: '/experiments', label: 'Experiments' },
  { to: '/documents', label: 'Documents' },
  { to: '/opportunities', label: 'Opportunities' },
  { to: '/state', label: 'Lab state' },
  { to: '/search', label: 'Search' },
  { to: '/literature', label: 'Literature' },
]

export default function Layout() {
  return (
    <div className="app">
      <nav className="sidebar" aria-label="Primary">
        <div className="brand"><BrandMark size="sidebar" /></div>
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
        <div className="footer">
          <OrganizationSwitcher hidePersonal />
          <UserButton />
        </div>
      </nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
