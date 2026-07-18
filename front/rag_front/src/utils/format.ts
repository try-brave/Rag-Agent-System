const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return '--'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }

  return dateFormatter.format(date)
}

export function formatFileSize(value?: number | null): string {
  if (value == null || Number.isNaN(value)) {
    return '--'
  }

  if (value < 1024) {
    return `${value} B`
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`
  }

  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

export function formatScore(value?: number | null): string {
  if (value == null || Number.isNaN(value)) {
    return '--'
  }

  return value.toFixed(4)
}

export function truncateText(value: string, length = 80): string {
  if (value.length <= length) {
    return value
  }

  return `${value.slice(0, length)}...`
}

export function createSessionId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }

  return `session-${Date.now()}`
}
