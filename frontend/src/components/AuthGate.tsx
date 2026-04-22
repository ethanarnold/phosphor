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
    <div style={{ maxWidth: 480, margin: '96px auto', padding: 24 }}>
      <div className="kicker">Setup</div>
      <h1 style={{ marginBottom: 16 }}>Create your lab</h1>
      <p className="muted" style={{ marginBottom: 24, lineHeight: 1.55 }}>
        Each Clerk organization maps to one Phosphor lab. We&apos;ll seed it
        using your organization name; you can rename later.
      </p>
      {error && <div className="error" style={{ marginBottom: 16 }}>{error}</div>}
      <button onClick={createLab} disabled={creating}>
        {creating ? 'Creating…' : `Create lab "${orgName}"`}
      </button>
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
      <div className="kicker">Setup</div>
      <h1 style={{ marginBottom: 16 }}>Organization required</h1>
      <p className="muted" style={{ marginBottom: 24, lineHeight: 1.55 }}>
        Phosphor is multi-tenant. Each organization is one lab — pick or
        create one to continue.
      </p>
      {userMemberships?.data && userMemberships.data.length > 0 && !showCreate ? (
        <>
          <p style={{ marginBottom: 8 }}>Switch to an existing organization:</p>
          <OrganizationSwitcher hidePersonal />
          <p style={{ marginTop: 24, marginBottom: 8 }}>Or:</p>
          <button onClick={() => setShowCreate(true)}>Create new organization</button>
        </>
      ) : showCreate ? (
        <>
          <CreateOrganization afterCreateOrganizationUrl="/" />
          <button className="ghost" onClick={() => setShowCreate(false)} style={{ marginTop: 12 }}>
            Cancel
          </button>
        </>
      ) : (
        <button onClick={() => setShowCreate(true)}>Create organization</button>
      )}
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
        <div className="error">{err.detail ?? 'Failed to load lab'}</div>
      </Centered>
    )
  }

  if (!lab) return <NoLabYet orgName={organization?.name ?? 'My lab'} />

  return <>{children}</>
}

function Centered({ children }: { children: ReactNode }) {
  return (
    <div style={{ maxWidth: 480, margin: '96px auto', padding: 24 }}>
      {typeof children === 'string' ? <p className="muted">{children}</p> : children}
    </div>
  )
}

export default function AuthGate({ children }: { children: ReactNode }) {
  return (
    <>
      <SignedOut>
        <Centered>
          <div className="kicker">Lab research tool</div>
          <h1 style={{ marginBottom: 16 }}>Phosphor</h1>
          <p className="muted" style={{ marginBottom: 24, lineHeight: 1.55 }}>
            Sign in to access your lab.
          </p>
          <div className="row">
            <SignInButton mode="modal">
              <button>Sign in</button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="ghost">Sign up</button>
            </SignUpButton>
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
