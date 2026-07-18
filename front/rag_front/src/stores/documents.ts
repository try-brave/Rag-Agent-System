import { defineStore } from 'pinia'

import {
  fetchDocumentChunks,
  fetchDocuments,
  fetchSplitterOptions,
  ingestTextDocument,
  rebuildDocumentIndex,
  uploadDocument,
  deleteDocument,
} from '@/api/modules/documents'
import { notifyError } from '@/api/http'
import type { ChunkItem, DocumentItem, SplitterOptionItem } from '@/types/api'

export const useDocumentStore = defineStore('documents', {
  state: () => ({
    documents: [] as DocumentItem[],
    splitters: [] as SplitterOptionItem[],
    chunksByDocument: {} as Record<string, ChunkItem[]>,
    loading: false,
    chunkLoading: false,
  }),
  getters: {
    totalChunks: (state) => state.documents.reduce((sum, item) => sum + item.chunk_count, 0),
  },
  actions: {
    async initialize() {
      await Promise.all([this.loadDocuments(), this.loadSplitters()])
    },
    async loadDocuments() {
      this.loading = true
      try {
        this.documents = await fetchDocuments()
      } catch (error) {
        notifyError(error, '加载文档列表失败')
      } finally {
        this.loading = false
      }
    },
    async loadSplitters() {
      try {
        this.splitters = await fetchSplitterOptions()
      } catch (error) {
        notifyError(error, '加载切分策略失败')
      }
    },
    async createTextDocument(payload: {
      filename: string
      content: string
      knowledge_base: string
      preferred_splitter?: string | null
    }) {
      const response = await ingestTextDocument(payload)
      await this.loadDocuments()
      return response.document
    },
    async createUploadDocument(payload: {
      file: File
      knowledge_base: string
      preferred_splitter?: string | null
    }) {
      const response = await uploadDocument(payload)
      await this.loadDocuments()
      return response.document
    },
    async refreshDocumentChunks(documentId: string) {
      this.chunkLoading = true
      try {
        const chunks = await fetchDocumentChunks(documentId)
        this.chunksByDocument[documentId] = chunks
        return chunks
      } catch (error) {
        notifyError(error, '加载文档切分结果失败')
        return []
      } finally {
        this.chunkLoading = false
      }
    },
    async triggerRebuild(documentId: string, preferredSplitter?: string | null) {
      const response = await rebuildDocumentIndex(documentId, preferredSplitter)
      await Promise.all([this.loadDocuments(), this.refreshDocumentChunks(documentId)])
      return response.document
    },
    async removeDocument(documentId: string) {
      await deleteDocument(documentId)
      await this.loadDocuments()
      delete this.chunksByDocument[documentId]
    },
  },
})
