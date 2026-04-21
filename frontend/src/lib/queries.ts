import { useQuery } from '@tanstack/react-query'
import { useApi, useApiKeyPrefix, type Lab, type LabState } from './api'

/** The current org's lab. Returns null cleanly when no lab exists yet. */
export function useLab() {
  const api = useApi()
  const keyPrefix = useApiKeyPrefix()
  return useQuery<Lab | null>({
    queryKey: [keyPrefix, 'lab'],
    queryFn: async () => {
      try {
        return await api<Lab>('/api/v1/labs')
      } catch (e) {
        const err = e as { status?: number }
        if (err.status === 404) return null
        throw e
      }
    },
  })
}

/** The current lab state. Returns null cleanly when no state exists yet. */
export function useLabState(labId: string | undefined) {
  const api = useApi()
  const keyPrefix = useApiKeyPrefix()
  return useQuery<LabState | null>({
    queryKey: [keyPrefix, 'lab-state', labId],
    enabled: !!labId,
    queryFn: async () => {
      try {
        return await api<LabState>(`/api/v1/labs/${labId}/state`)
      } catch (e) {
        const err = e as { status?: number }
        if (err.status === 404) return null
        throw e
      }
    },
  })
}
