import { useAuth } from '@clerk/clerk-react'
import { useCallback, useMemo } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export interface ApiError {
  status: number
  detail: string
}

// FastAPI returns `detail` as a string for HTTPException, but an array of
// Pydantic error objects for 422. Flatten so UI code can render directly.
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

export interface FetchOptions extends Omit<RequestInit, 'body'> {
  body?: BodyInit | null | object
}

async function rawFetch<T>(
  token: string | null,
  path: string,
  init: FetchOptions = {},
): Promise<T> {
  const { body, ...rest } = init
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string> | undefined),
  }
  if (!isFormData && body !== undefined && body !== null && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let serializedBody: BodyInit | null | undefined
  if (body == null) {
    serializedBody = body as null | undefined
  } else if (
    isFormData ||
    typeof body === 'string' ||
    body instanceof Blob ||
    body instanceof ArrayBuffer ||
    body instanceof URLSearchParams
  ) {
    serializedBody = body as BodyInit
  } else {
    serializedBody = JSON.stringify(body)
  }

  const resp = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers,
    body: serializedBody,
  })
  if (!resp.ok) {
    let detail: string = resp.statusText
    try {
      const errBody = await resp.json()
      detail = formatDetail(errBody?.detail) ?? detail
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
  return useCallback(
    async <T,>(path: string, init?: FetchOptions): Promise<T> => {
      const token = await getToken()
      return rawFetch<T>(token, path, init)
    },
    [getToken],
  )
}

/** Stable cache-key prefix per active org so React Query refetches on switch. */
export function useApiKeyPrefix(): string {
  const { orgId, userId } = useAuth()
  return useMemo(() => `${orgId ?? 'noorg'}:${userId ?? 'nouser'}`, [orgId, userId])
}

// ---------- Lab ----------

export interface Lab {
  id: string
  clerk_org_id: string
  name: string
  created_at: string
  updated_at: string
}

export interface LabCreate {
  name: string
}

// ---------- Lab state ----------

export interface Equipment {
  name: string
  capabilities: string[]
  limitations: string | null
}

export interface Technique {
  name: string
  proficiency: 'expert' | 'competent' | 'learning'
  notes: string | null
}

export interface Expertise {
  domain: string
  confidence: 'high' | 'medium' | 'low'
}

export interface Organism {
  name: string
  strains: string[]
  notes: string | null
}

export interface Reagent {
  name: string
  quantity: string | null
  notes: string | null
}

export interface ExperimentSummary {
  technique: string
  outcome: 'success' | 'partial' | 'failed'
  insight: string
}

export interface ResourceConstraints {
  budget_notes: string | null
  time_constraints: string | null
  personnel_notes: string | null
}

export interface LabStateData {
  equipment: Equipment[]
  techniques: Technique[]
  expertise: Expertise[]
  organisms: Organism[]
  reagents: Reagent[]
  experimental_history: ExperimentSummary[]
  resource_constraints: ResourceConstraints
  signal_count: number
}

export interface LabState {
  id: string
  lab_id: string
  version: number
  state: LabStateData
  token_count: number | null
  created_at: string
  created_by: string | null
}

export interface LabStateHistory {
  states: LabState[]
  total: number
}

// ---------- Experiments ----------

export type Outcome = 'success' | 'partial' | 'failed'

export interface ExperimentEntry {
  date?: string | null
  technique: string
  outcome: Outcome
  notes: string
  equipment_used?: string[]
  organisms_used?: string[]
  reagents_used?: string[]
}

export interface ExperimentCreateResponse {
  signal_id: string
  experiment: ExperimentEntry
  elapsed_ms: number | null
}

export interface QuickLogRequest {
  text: string
  outcome_hint?: Outcome | null
}

export interface BulkExperimentRequest {
  entries: ExperimentEntry[]
}

export interface BulkExperimentResponse {
  created: ExperimentCreateResponse[]
  failed: { index: string; error: string }[]
}

// ---------- Documents ----------

export interface Document {
  id: string
  lab_id: string
  filename: string
  content_type: string
  byte_size: number
  status: string
  chunk_count: number
  signal_id: string | null
  parse_error: string | null
  created_at: string
  created_by: string
}

export interface DocumentList {
  documents: Document[]
  total: number
}

// ---------- Opportunities ----------

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

export interface OpportunityList {
  opportunities: Opportunity[]
  total: number
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

// ---------- Protocols ----------

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
  status: 'generated' | 'reviewed' | 'archived'
  created_at: string
  created_by: string
}

// ---------- Feedback ----------

export type CorrectionType = 'add' | 'remove' | 'update'
export type CorrectionField =
  | 'equipment'
  | 'techniques'
  | 'expertise'
  | 'organisms'
  | 'reagents'
  | 'resource_constraints'

export interface StateCorrection {
  correction_type: CorrectionType
  field: CorrectionField
  item_name: string
  new_value?: Record<string, unknown> | null
  reason?: string | null
}

export interface OpportunityFeedback {
  decision: 'accept' | 'reject'
  reason?: string | null
}

export interface FeedbackResponse {
  signal_id: string
  correction?: StateCorrection | null
  opportunity_id?: string | null
  decision?: 'accept' | 'reject' | null
  created_at: string
}

// ---------- Search ----------

export interface SearchHit {
  kind: 'signal' | 'paper'
  id: string
  score: number
  snippet: string
  matched_by: 'keyword' | 'embedding' | 'both'
  signal_type: string | null
  title: string | null
  created_at: string
}

export interface SearchResponse {
  query: string
  hits: SearchHit[]
  total: number
}

// ---------- Literature ----------

export interface ScanRequest {
  query_terms: string[]
  mesh_terms?: string[]
  author_affiliations?: string[]
  journals?: string[]
  field_of_study?: string | null
  max_results?: number
  sources?: ('pubmed' | 'semantic_scholar')[]
}

export interface LiteratureScan {
  id: string
  lab_id: string
  scan_type: string
  query_params: Record<string, unknown>
  papers_found: number
  papers_new: number
  opportunities_extracted: number
  status: string
  error_message: string | null
  started_at: string
  completed_at: string | null
  triggered_by: string
}

export interface ScanList {
  scans: LiteratureScan[]
  total: number
}

// ---------- Agents (reviewer / directions / strengthen) ----------

export type AgentStatus = 'queued' | 'running' | 'complete' | 'error'
export type AgentMessageRole = 'system' | 'user' | 'assistant' | 'tool'

export interface AgentMessageView {
  id: string
  seq: number
  role: AgentMessageRole
  content: string | null
  tool_name: string | null
  tool_args_json: Record<string, unknown> | null
  tool_result_json: Record<string, unknown> | null
  created_at: string
}

export interface AgentCreateResponse {
  session_id: string
  status: AgentStatus
}

export interface AgentDetail {
  session_id: string
  status: AgentStatus
  input_text: string
  final_answer: string | null
  error: string | null
  turn_count: number
  model: string | null
  messages: AgentMessageView[]
  created_at: string
  completed_at: string | null
}

// Backward-compat aliases — Review.tsx imports these names.
export type ReviewerCreateResponse = AgentCreateResponse
export type ReviewerDetail = AgentDetail

// ---------- Metrics ----------

export interface EventTypeStats {
  event_type: string
  count: number
  avg_duration_ms: number | null
  p95_duration_ms: number | null
}

export interface AdoptionMetrics {
  since: string
  total_events: number
  by_type: EventTypeStats[]
  recent: Record<string, unknown>[]
}
