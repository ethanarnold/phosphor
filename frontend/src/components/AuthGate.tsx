import {
  CreateOrganization,
  OrganizationSwitcher,
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  useOrganization,
  useOrganizationList,
} from '@clerk/clerk-react'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { useApi } from '../lib/api'
import { useLab } from '../lib/queries'

function NoLabYet({ orgName }: { orgName: string }) {
  const api = useApi()
  const qc = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createLab = async () => {
    setCreating(true)
    setError(null)
    try {
      await api('/api/v1/labs', { method: 'POST', body: { name: orgName } })
      await qc.invalidateQueries()
    } catch (e) {
      const err = e as { detail?: string }
      setError(err.detail ?? 'Could not create lab')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div style={{ maxWidth: 480, margin: '4rem auto' }}>
      <div className="card">
        <h2>Create your lab</h2>
        <p className="muted">
          Each Clerk organization maps to one Phosphor lab. We&apos;ll seed it
          using your organization name; you can rename later.
        </p>
        {error && <div className="error" style={{ marginBottom: 8 }}>{error}</div>}
        <button onClick={createLab} disabled={creating}>
          {creating ? 'Creating…' : `Create lab "${orgName}"`}
        </button>
      </div>
    </div>
  )
}

function OrgRequired({ children }: { children: ReactNode }) {
  const { isLoaded, organization } = useOrganization()
  const { userMemberships } = useOrganizationList({ userMemberships: true })
  const [showCreate, setShowCreate] = useState(false)

  if (!isLoaded) {
    return <Centered>Loading…</Centered>
  }

  if (organization) return <>{children}</>

  return (
    <Centered>
      <div className="card">
        <h2>Organization required</h2>
        <p className="muted">
          Phosphor is multi-tenant. Each organization is one lab — pick or
          create one to continue.
        </p>
        {userMemberships?.data && userMemberships.data.length > 0 && !showCreate ? (
          <>
            <p>Switch to an existing organization:</p>
            <OrganizationSwitcher hidePersonal />
            <p style={{ marginTop: '1rem' }}>Or:</p>
            <button onClick={() => setShowCreate(true)}>Create new organization</button>
          </>
        ) : showCreate ? (
          <>
            <CreateOrganization afterCreateOrganizationUrl="/" />
            <button className="ghost" onClick={() => setShowCreate(false)} style={{ marginTop: 8 }}>
              Cancel
            </button>
          </>
        ) : (
          <button onClick={() => setShowCreate(true)}>Create organization</button>
        )}
      </div>
    </Centered>
  )
}

function LabRequired({ children }: { children: ReactNode }) {
  const { organization } = useOrganization()
  const { data: lab, isLoading, error, refetch } = useLab()

  // Refetch on org switch — useLab() key includes orgId so this is implicit,
  // but we nudge here to clear any stale 401 that beat the new token.
  useEffect(() => {
    refetch()
  }, [organization?.id, refetch])

  if (isLoading) return <Centered>Loading lab…</Centered>

  if (error) {
    const err = error as { detail?: string }
    return (
      <Centered>
        <div className="card">
          <div className="error">{err.detail ?? 'Failed to load lab'}</div>
        </div>
      </Centered>
    )
  }

  if (!lab) return <NoLabYet orgName={organization?.name ?? 'My lab'} />

  return <>{children}</>
}

function Centered({ children }: { children: ReactNode }) {
  return (
    <div style={{ maxWidth: 480, margin: '4rem auto' }}>
      {typeof children === 'string' ? <div className="card">{children}</div> : children}
    </div>
  )
}

export default function AuthGate({ children }: { children: ReactNode }) {
  return (
    <>
      <SignedOut>
        <Centered>
          <div className="card">
            <h2>Phosphor</h2>
            <p className="muted">Sign in to access your lab.</p>
            <div className="row">
              <SignInButton mode="modal">
                <button>Sign in</button>
              </SignInButton>
              <SignUpButton mode="modal">
                <button className="ghost">Sign up</button>
              </SignUpButton>
            </div>
          </div>
        </Centered>
      </SignedOut>
      <SignedIn>
        <OrgRequired>
          <LabRequired>{children}</LabRequired>
        </OrgRequired>
      </SignedIn>
    </>
  )
}
