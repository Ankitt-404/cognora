export const API = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
export const TOKEN_KEY = 'cognora_token'
export function responseMessage(body: unknown, fallback: string) {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = body.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) => item && typeof item === 'object' && 'msg' in item ? item.msg : '')
        .filter((message): message is string => typeof message === 'string' && message.length > 0)
        .join(', ') || fallback
    }
  }
  return fallback
}