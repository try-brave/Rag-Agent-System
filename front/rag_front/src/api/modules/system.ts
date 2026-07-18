import type { HealthResponse } from '@/types/api'
import { backendOrigin, http } from '@/api/http'

export async function fetchSystemHealth(): Promise<HealthResponse> {
  const url = backendOrigin ? `${backendOrigin}/health` : '/health'
  const { data } = await http.get<HealthResponse>(url, {
    baseURL: '',
  })
  return data
}
