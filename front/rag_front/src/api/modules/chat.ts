import type {
  ChatHistoryItem,
  ChatResponse,
  ChatStreamEventName,
  SessionClearResponse,
  SessionSummaryItem,
} from '@/types/api'
import { apiBaseUrl, http } from '@/api/http'

export interface ChatPayload {
  session_id: string
  message: string
  top_k: number
}

export interface ChatStreamEvent<T = unknown> {
  event: ChatStreamEventName
  data: T
}

export interface StreamHandlers {
  onEvent: (event: ChatStreamEvent) => void
  signal?: AbortSignal
}

export async function fetchSessions(limit = 50): Promise<SessionSummaryItem[]> {
  const { data } = await http.get<SessionSummaryItem[]>('/chat/sessions', { params: { limit } })
  return data
}

export async function fetchSessionHistory(sessionId: string, limit = 100): Promise<ChatHistoryItem[]> {
  const { data } = await http.get<ChatHistoryItem[]>(`/chat/sessions/${sessionId}/history`, {
    params: { limit },
  })
  return data
}

export async function clearSession(sessionId: string): Promise<SessionClearResponse> {
  const { data } = await http.delete<SessionClearResponse>(`/chat/sessions/${sessionId}`)
  return data
}

export async function sendChat(payload: ChatPayload): Promise<ChatResponse> {
  const { data } = await http.post<ChatResponse>('/chat', payload)
  return data
}

function parseSseChunk(rawChunk: string): ChatStreamEvent[] {
  const packets = rawChunk.split('\n\n').filter(Boolean)
  return packets.flatMap((packet) => {
    const lines = packet.split('\n').filter(Boolean)
    const eventLine = lines.find((line) => line.startsWith('event:'))
    const dataLines = lines.filter((line) => line.startsWith('data:'))

    if (!eventLine || dataLines.length === 0) {
      return []
    }

    const event = eventLine.slice('event:'.length).trim() as ChatStreamEventName
    const dataText = dataLines.map((line) => line.slice('data:'.length).trim()).join('\n')

    try {
      return [{ event, data: JSON.parse(dataText) }]
    } catch {
      return [{ event, data: dataText }]
    }
  })
}

export async function streamChat(payload: ChatPayload, handlers: StreamHandlers): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || '流式对话请求失败')
  }

  if (!response.body) {
    throw new Error('浏览器当前环境不支持流式读取')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      for (const event of parseSseChunk(`${part}\n\n`)) {
        handlers.onEvent(event)
      }
    }
  }

  if (buffer.trim()) {
    for (const event of parseSseChunk(buffer)) {
      handlers.onEvent(event)
    }
  }
}
