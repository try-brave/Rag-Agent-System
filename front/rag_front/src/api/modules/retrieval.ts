import type { RetrievalSearchResponse } from '@/types/api'
import { http } from '@/api/http'

export async function searchRetrieval(query: string, top_k: number): Promise<RetrievalSearchResponse> {
  const { data } = await http.post<RetrievalSearchResponse>('/retrieval/search', {
    query,
    top_k,
  })
  return data
}
