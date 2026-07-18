export interface ServiceHealthItem {
  ok: boolean
  error: string | null
}

export interface HealthResponse {
  ok: boolean
  services: Record<string, ServiceHealthItem>
}

export interface SplitterOptionItem {
  name: string
  description: string
}

export interface DocumentItem {
  id: string
  knowledge_base: string
  filename: string
  file_type: string
  source_path: string | null
  file_size: number | null
  status: string
  chunk_count: number
  summary: string | null
  created_at: string
  updated_at: string
}

export interface DocumentIngestResponse {
  document: DocumentItem
  message: string
}

export interface ChunkItem {
  id: string
  document_id: string
  chunk_index: number
  content: string
  metadata_json: Record<string, unknown>
  token_count: number
  page_number: number | null
  start_offset: number | null
  end_offset: number | null
  vector_id: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface RetrievalHitItem {
  chunk_id: string | null
  document_id: string | null
  filename: string | null
  file_type: string | null
  chunk_index: number | null
  content: string
  score: number
  vector_score: number | null
  bm25_score: number | null
  fused_score: number | null
  retrieval_source: string | null
  retrieval_sources: string[]
  rank_vector: number | null
  rank_bm25: number | null
  rank_fused: number | null
  splitter_name: string | null
  parser_name: string | null
  section_type: string | null
  section_title: string | null
  page_number: number | null
  source_path: string | null
  start_offset: number | null
  end_offset: number | null
}

export interface RetrievalSearchResponse {
  items: RetrievalHitItem[]
}

export interface SourceChunkItem extends RetrievalHitItem {
  ref_id: number
}

export interface ChatResponse {
  session_id: string
  answer: string
  route: string
  latency_ms: number
  source_chunks: SourceChunkItem[]
  created_at: string
}

export interface ChatHistoryItem {
  id: string
  session_id: string | null
  user_question: string
  answer: string | null
  route: string
  latency_ms: number | null
  source_chunks: SourceChunkItem[]
  created_at: string
  updated_at: string
}

export interface SessionSummaryItem {
  session_id: string
  latest_question: string
  latest_answer: string | null
  message_count: number
  updated_at: string
}

export interface SessionClearResponse {
  session_id: string
  deleted_query_log_count: number
  cleared_memory: boolean
}

export type ChatStreamEventName =
  | 'status'
  | 'token'
  | 'tool_call'
  | 'tool_result'
  | 'tool_error'
  | 'sources'
  | 'error'
  | 'done'

export interface ChatToolEvent {
  type: 'tool_call' | 'tool_result' | 'tool_error' | 'status' | 'error'
  step?: string
  tool_name?: string
  tool_call_id?: string
  status?: string
  content?: string
  message?: string
  args?: Record<string, unknown>
  session_id?: string
  phase?: string
  timestamp: string
}

export interface ChatTurn {
  id: string
  sessionId: string
  userQuestion: string
  answer: string
  route: string
  latencyMs: number | null
  sourceChunks: SourceChunkItem[]
  createdAt: string
  updatedAt: string
  pending?: boolean
  failed?: boolean
  errorMessage?: string
  events: ChatToolEvent[]
}
