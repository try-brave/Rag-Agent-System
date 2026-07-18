import type { ChunkItem } from '@/types/api'
import { http } from '@/api/http'

export interface UpdateChunkPayload {
  content?: string
  enabled?: boolean
  metadata_json?: Record<string, unknown> | null
}

export async function fetchChunks(params?: {
  document_id?: string
  limit?: number
}): Promise<ChunkItem[]> {
  const { data } = await http.get<ChunkItem[]>('/chunks', { params })
  return data
}

export async function updateChunk(chunkId: string, payload: UpdateChunkPayload): Promise<ChunkItem> {
  const { data } = await http.patch<ChunkItem>(`/chunks/${chunkId}`, payload)
  return data
}

export async function deleteChunk(chunkId: string): Promise<void> {
  await http.delete(`/chunks/${chunkId}`)
}
