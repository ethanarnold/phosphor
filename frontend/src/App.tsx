import { Route, Routes } from 'react-router-dom'
import AuthGate from './components/AuthGate'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import Experiments from './pages/Experiments'
import LabStatePage from './pages/LabState'
import Literature from './pages/Literature'
import OpportunityDetail from './pages/OpportunityDetail'
import Opportunities from './pages/Opportunities'
import Search from './pages/Search'

export default function App() {
  return (
    <AuthGate>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="experiments" element={<Experiments />} />
          <Route path="documents" element={<Documents />} />
          <Route path="opportunities" element={<Opportunities />} />
          <Route path="opportunities/:opportunityId" element={<OpportunityDetail />} />
          <Route path="state" element={<LabStatePage />} />
          <Route path="search" element={<Search />} />
          <Route path="literature" element={<Literature />} />
          <Route
            path="*"
            element={
              <div className="card">
                <h2>Not found</h2>
                <p className="muted">The page you requested doesn&apos;t exist.</p>
              </div>
            }
          />
        </Route>
      </Routes>
    </AuthGate>
  )
}
