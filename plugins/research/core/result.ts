export type OpResult<T> = { ok: true; value: T; warnings: string[] } | { ok: false; errors: string[] }

export function ok<T>(value: T, warnings: string[] = []): OpResult<T> {
  return { ok: true, value, warnings }
}

export function fail<T>(...errors: string[]): OpResult<T> {
  return { ok: false, errors }
}
