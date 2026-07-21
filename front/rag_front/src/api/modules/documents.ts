import type {
  ChunkItem,
  DocumentIngestResponse,
  DocumentItem,
  SplitterOptionItem,
} from '@/types/api'
import { http } from '@/api/http'

export interface TextIngestPayload {
  filename: string
  content: string
  knowledge_base: string
  preferred_splitter?: string | null
}

export interface UploadDocumentPayload {
  file: File
  knowledge_base: string
  preferred_splitter?: string | null
}

export interface BatchUploadPayload {
  files: File[]
  knowledge_base: string
  preferred_splitter?: string | null
}

export interface BatchUploadItem {
  document: DocumentItem | null
  message: string
  error: string | null
}

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const { data } = await http.get<DocumentItem[]>('/documents')
  return data
}

export async function fetchSplitterOptions(): Promise<SplitterOptionItem[]> {
  const { data } = await http.get<SplitterOptionItem[]>('/documents/splitters/options')
  return data
}

export async function ingestTextDocument(payload: TextIngestPayload): Promise<DocumentIngestResponse> {
  const { data } = await http.post<DocumentIngestResponse>('/documents/ingest-text', payload)
  return data
}

export async function uploadDocument(payload: UploadDocumentPayload): Promise<DocumentIngestResponse> {
  const formData = new FormData()
  formData.append('file', payload.file)
  formData.append('knowledge_base', payload.knowledge_base)
  if (payload.preferred_splitter) {
    formData.append('preferred_splitter', payload.preferred_splitter)
  }

  const { data } = await http.post<DocumentIngestResponse>('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function batchUploadDocuments(payload: BatchUploadPayload): Promise<BatchUploadItem[]> {
  const formData = new FormData()
  for (const file of payload.files) {
    formData.append('files', file)
  }
  formData.append('knowledge_base', payload.knowledge_base)
  if (payload.preferred_splitter) {
    formData.append('preferred_splitter', payload.preferred_splitter)
  }

  const { data } = await http.post<BatchUploadItem[]>('/documents/batch-upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function rebuildDocumentIndex(
  documentId: string,
  preferred_splitter?: string | null,
): Promise<DocumentIngestResponse> {
  const { data } = await http.post<DocumentIngestResponse>(
    `/documents/${documentId}/rebuild-index`,
    { preferred_splitter: preferred_splitter || null },
  )
  return data
}

export async function fetchDocumentChunks(documentId: string): Promise<ChunkItem[]> {
  const { data } = await http.get<ChunkItem[]>(`/documents/${documentId}/chunks`)
  return data
}

export async function deleteDocument(documentId: string): Promise<void> {
  await http.delete(`/documents/${documentId}`)
}
