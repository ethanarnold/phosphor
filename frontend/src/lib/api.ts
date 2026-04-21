import { useAuth } from '@clerk/clerk-react'
import { useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export interface ApiError {
  status: number
  detail: string
}

// FastAPI returns `detail` as a string for HTTPException, but an array of
// Pydantic error objects for 422. Flatten to a string so UI code can render
// it directly without crashing on an unexpected shape.
function formatDetail(detail: unknown): string | null {
  if (detail == null) return null
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        if (typeof e === 'string') return e
        if (e && typeof e === 'object') {
          const { loc, msg } = e as { loc?: unknown[]; msg?: string }
          const locStr = Array.isArray(loc) ? loc.join('.') : ''
          return [locStr, msg].filter(Boolean).join(': ')
        }
        return JSON.stringify(e)
      })
      .join('; ')
  }
  if (typeof detail === 'object') return JSON.stringify(detail)
  return String(detail)
}

async function rawFetch<T>(
  token: string | null,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!resp.ok) {
    let detail: string = resp.statusText
    try {
      const body = await resp.json()
      detail = formatDetail(body?.detail) ?? detail
    } catch {
      /* ignore */
    }
    const err: ApiError = { status: resp.status, detail }
    throw err
  }
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

/** React hook returning an authed fetch bound to the current Clerk token. */
export function useApi() {
  const { getToken } = useAuth()
  const apiFetch = useCallback(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const token = await getToken()
      return rawFetch<T>(token, path, init)
    },
    [getToken],
  )
  return apiFetch
}

export interface Lab {
  id: string
  clerk_org_id: string
  name: string
  created_at: string
}

export interface Opportunity {
  id: string
  lab_id: string
  description: string
  required_equipment: string[]
  required_techniques: string[]
  required_expertise: string[]
  estimated_complexity: string
  source_paper_ids: string[]
  quality_score: number | null
  status: string
  created_at: string
  updated_at: string
}

export type EquipmentStatus = 'have' | 'acquire' | 'cannot'
export type TechniqueStatus = 'practiced' | 'learnable' | 'gap'
export type ExpertiseStatus = 'strong' | 'adjacent' | 'gap'

export interface MatchScore {
  feasibility: number
  alignment: number
  composite: number
  breakdown: {
    equipment: Record<string, EquipmentStatus>
    techniques: Record<string, TechniqueStatus>
    expertise: Record<string, ExpertiseStatus>
  }
}

export interface RankedOpportunity {
  opportunity: Opportunity
  score: MatchScore
}

export interface RankedOpportunityList {
  items: RankedOpportunity[]
  total: number
}

export interface GapAnalysis {
  opportunity_id: string
  missing_equipment: string[]
  acquirable_equipment: string[]
  skill_gaps: string[]
  learnable_skills: string[]
  expertise_gaps: string[]
  estimated_effort: 'low' | 'medium' | 'high'
  closable_via_collaboration: string[]
}

export interface ProtocolPhase {
  name: string
  steps: string[]
  duration_estimate: string | null
  materials_used: string[]
}

export interface ProtocolContent {
  phases: ProtocolPhase[]
  materials: string[]
  expected_outcomes: string[]
  flagged_gaps: string[]
  citations: string[]
}

export interface Protocol {
  id: string
  lab_id: string
  opportunity_id: string
  title: string
  content: ProtocolContent
  lab_state_version: number
  llm_model: string
  prompt_version: string
  status: string
  created_at: string
  created_by: string
}
