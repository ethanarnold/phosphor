import {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  UserButton,
  useAuth,
  useOrganization,
  useOrganizationList,
  OrganizationSwitcher,
  CreateOrganization,
} from '@clerk/clerk-react'
import { useEffect, useState } from 'react'
import RankedOpportunities from './pages/RankedOpportunities'

function TokenDisplay() {
  const { getToken } = useAuth()
  const { organization } = useOrganization()
  const [token, setToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const fetchToken = async () => {
    const t = await getToken()
    setToken(t)
  }

  useEffect(() => {
    fetchToken()
  }, [organization])

  const copyToken = () => {
    if (token) {
      navigator.clipboard.writeText(token)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const copyCurl = () => {
    if (token) {
      const curl = `curl -X POST http://localhost:8000/api/v1/labs \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${token}" \\
  -d '{"name": "My Research Lab"}'`
      navigator.clipboard.writeText(curl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (!organization) {
    return null
  }

  return (
    <div className="card">
      <h2>Your JWT Token</h2>
      <p>Organization: <strong>{organization.name}</strong> ({organization.id})</p>
      <div>
        <button onClick={fetchToken}>Refresh Token</button>
        <button onClick={copyToken}>{copied ? 'Copied!' : 'Copy Token'}</button>
        <button onClick={copyCurl}>Copy as curl</button>
      </div>
      {token && (
        <>
          <h3>Token:</h3>
          <pre className="token-box">{token}</pre>
          <h3>Example curl:</h3>
          <pre>{`curl -X POST http://localhost:8000/api/v1/labs \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${token.substring(0, 20)}..." \\
  -d '{"name": "My Research Lab"}'`}</pre>
        </>
      )}
    </div>
  )
}

type Tab = 'opportunities' | 'token'

function OrganizationRequired() {
  const { organizationList, isLoaded } = useOrganizationList()
  const { organization } = useOrganization()
  const [showCreate, setShowCreate] = useState(false)
  const [tab, setTab] = useState<Tab>('opportunities')

  if (!isLoaded) {
    return <div className="card">Loading...</div>
  }

  if (organization) {
    return (
      <>
        <div className="card">
          <button
            onClick={() => setTab('opportunities')}
            style={{
              background: tab === 'opportunities' ? '#4f46e5' : '#94a3b8',
            }}
          >
            Ranked opportunities
          </button>
          <button
            onClick={() => setTab('token')}
            style={{ background: tab === 'token' ? '#4f46e5' : '#94a3b8' }}
          >
            JWT token
          </button>
        </div>
        {tab === 'opportunities' ? <RankedOpportunities /> : <TokenDisplay />}
      </>
    )
  }

  if (showCreate) {
    return (
      <div className="card">
        <h2>Create Organization</h2>
        <p>The API requires an organization context for multi-tenancy.</p>
        <CreateOrganization afterCreateOrganizationUrl="/" />
        <button onClick={() => setShowCreate(false)} style={{ marginTop: '1rem' }}>
          Cancel
        </button>
      </div>
    )
  }

  return (
    <div className="card">
      <h2>Organization Required</h2>
      <p>The Phosphor API requires an organization context. Each organization = one lab.</p>

      {organizationList && organizationList.length > 0 ? (
        <>
          <p>Select an existing organization:</p>
          <OrganizationSwitcher />
          <p style={{ marginTop: '1rem' }}>Or:</p>
        </>
      ) : null}

      <button onClick={() => setShowCreate(true)}>Create New Organization</button>
    </div>
  )
}

export default function App() {
  return (
    <div>
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1>Phosphor Auth Test</h1>
          <SignedIn>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <OrganizationSwitcher />
              <UserButton />
            </div>
          </SignedIn>
        </div>

        <SignedOut>
          <p>Sign in or create an account to test the API authentication.</p>
          <SignInButton mode="modal">
            <button>Sign In</button>
          </SignInButton>
          <SignUpButton mode="modal">
            <button>Sign Up</button>
          </SignUpButton>
        </SignedOut>
      </div>

      <SignedIn>
        <OrganizationRequired />
      </SignedIn>

      <div className="card">
        <h2>Setup Checklist</h2>
        <ol>
          <li>Sign up / Sign in above</li>
          <li>Create an organization (required for multi-tenancy)</li>
          <li>Copy the JWT token</li>
          <li>Use it with curl or paste into your API client</li>
        </ol>

        <h3>Backend Environment Variables</h3>
        <pre>{`CLERK_SECRET_KEY=sk_test_...
CLERK_JWKS_URL=https://your-instance.clerk.accounts.dev/.well-known/jwks.json
ANTHROPIC_API_KEY=sk-ant-...`}</pre>
      </div>
    </div>
  )
}
