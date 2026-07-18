import axios from 'axios'
import { ElMessage } from 'element-plus'

const DEFAULT_API_BASE_URL = '/api/v1'

export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
export const backendOrigin = apiBaseUrl.endsWith('/api/v1')
  ? apiBaseUrl.slice(0, -'/api/v1'.length) || ''
  : ''

function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }

    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg || JSON.stringify(item)).join('；')
    }

    return error.message || '请求失败'
  }

  if (error instanceof Error) {
    return error.message
  }

  return '请求失败'
}

export function notifyError(error: unknown, fallback = '操作失败'): string {
  const message = extractErrorMessage(error) || fallback
  ElMessage.error(message)
  return message
}

export const http = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30000,
})

http.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error),
)
